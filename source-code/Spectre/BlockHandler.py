''' 
    A handler for Block.py that takes a collection of blocks (which 
    only reference parents) as input data. It uses a doubly-linked
    tree to determine precedent relationships efficiently, and it can
    use that precedence relationship to produce a reduced/robust  pre-
    cedence relationship as output (the spectre precedence relationship 
    between blocks.
    
    Another handler will extract a coherent/robust list of non-conflict-
    ing transactions from a reduced/robust BlockHandler object.
'''
from Block import *
import random

class BlockHandler(object):
    def __init__(self):
        #print("Initializing")
        # Initialize a BlockHandler object. 
        self.data = None
        self.blocks = {} # Set of blocks (which track parents)
        self.family = {} # Doubly linked list tracks parent-and-child links
        self.invDLL = {} # subset of blocks unlikely to be re-orged
        self.roots = [] # list of root blockIdents
        self.leaves = [] # list of leaf blockIdents
        self.antichains = []
        self.vids = []
        self.antichainCutoff = 600 # stop re-orging after this many layers
        self.pendingVotes = {}
        self.votes = {}
        self.oldVotes = {}
    def sumPendingVote(self, vid, touched):
        for (xid,yid) in zip(self.vids,self.vids):
            if (vid, xid, yid) in self.pendingVotes:
                if self.pendingVotes[(vid,xid,yid)] > 0:
                    touched = self.voteFor((vid,xid,yid), touched)
                elif self.pendingVotes[(vid,xid,yid)] <0:
                    touched = self.voteFor((vid,yid,xid), touched)
                else:
                    self.votes.update({(vid,xid,yid): 0, (vid,yid,xid): 0})
                    touched.update({(vid,xid,yid): True, (vid,yid,xid): True})
        return touched

    def voteFor(self, votingIdents, touched):
        (vid, xid, yid) = votingIdents
        self.votes.update({(vid,xid,yid):1, (vid,yid,xid):-1})
        touched.update({(vid,xid,yid):True, (vid,yid,xid):True})
        self.transmitVote((vid,xid,yid))
        return touched

    def transmitVote(self, votingIdents):
        (vid, xid, yid) = votingIdents
        q = deque()
        for wid in self.blocks[vid].parents:
            if wid in self.vids:
                q.append(wid)
        while(len(q)>0):
            wid = q.popleft()
            if (wid,xid,yid) not in self.pendingVotes:
                self.pendingVotes.update({(wid,xid,yid):0})
            if (wid,yid,xid) not in self.pendingVotes:
                self.pendingVotes.update({(wid,yid,xid):0})
            self.pendingVotes[(wid,xid,yid)]+=1
            self.pendingVotes[(wid,yid,xid)]-=1
            #print(self.blocks[wid].parents)
            for pid in self.blocks[wid].parents:
                if pid in self.vids:
                    q.append(pid)

        
    def _addBlock(self, b):
        #print("Adding block")
        # Take a single block b and add to self.blocks, record family
        # relations, update leaf monitor, update root monitor if nec-
        # essary

        diffDict = {copy.deepcopy(b.ident):copy.deepcopy(b)}
        
        try:
            assert b.ident not in self.blocks
        except AssertionError:
            print("Woops, tried to add a block with ident in self.blocks, overwriting old block")
        self.blocks.update(diffDict)

        try:
            assert b.ident not in self.leaves
        except AssertionError:
            print("Woops, tried to add a block to leaf set that is already in the leafset, aborting.")
        self.leaves.append(b.ident) # New block is always a leaf
                
        try:
            assert b.ident not in self.family
        except AssertionError:
            print("woops, tried to add a block that already has a recorded family history, aborting.")
        self.family.update({b.ident:{"parents":b.parents, "children":[]}}) 
        # Add fam history fam (new blocks have no children yet)

        # Now update each parent's family history to reflect the new child
        if b.parents is not None:
            if len(b.parents)>0:
                for parentIdent in b.parents:
                    if parentIdent not in self.family:
                        # This should never occur.
                        print("Hey, what? confusedTravolta.gif... parentIdent not in self.family, parent not correct somehow.")
                        self.family.update({parentIdent:{}})

                    if "parents" not in self.family[parentIdent]:
                        # This should never occur.
                        print("Hey, what? confusedTravolta.gif... family history of parent lacks sub-dict for parentage, parent not correct somehow")
                        self.family[parentIdent].update({"parents":[]})

                    if "children" not in self.family[parentIdent]:
                        # This should never occur.
                        print("Hey, what? confusedTravolta.gif... family history of parent lacks sub-dict for children, parent not correct somehow")
                        self.family[parentIdent].update({"children":[]})

                    if self.blocks[parentIdent].parents is not None:
                        for pid in self.blocks[parentIdent].parents:
                            if pid not in self.family[parentIdent]["parents"]:
                                self.family[parentIdent]["parents"].append(pid)
                    #for p in self.blocks[parentIdent].parents: self.family[parentIdent]["parents"].append(p)
                    
                    # Update "children" sub-dict of family history of parent
                    self.family[parentIdent]["children"].append(b.ident)

                    # If the parent was previously a leaf, it is no longer
                    if parentIdent in self.leaves:
                        self.leaves.remove(parentIdent)

            else:
                if b.ident not in self.roots:
                    self.roots.append(b.ident)
                if b.ident not in self.leaves:
                    self.leaves.append(b.ident)
                if b.ident not in self.family:
                    self.family.update({b.ident:{"parents":{}, "children":{}}})

        else:
            if b.ident not in self.roots:
                self.roots.append(b.ident)
            if b.ident not in self.leaves:
                self.leaves.append(b.ident)
            if b.ident not in self.family:
                self.family.update({b.ident:{"parents":{}, "children":{}}})
    
    def _hasAncestor(self, xid, yid):
        # Return true if y is an ancestor of x
        assert xid in self.blocks
        assert yid in self.blocks
        q = deque()
        found = False
        if self.blocks[xid].parents is not None:
            for pid in self.blocks[xid].parents:
                if pid==yid:
                    found = True
                    break
                q.append(pid)
            while(len(q)>0 and not found):
                xid = q.popleft()
                if self.blocks[xid].parents is not None:
                    if len(self.blocks[xid].parents) > 0:
                        for pid in self.blocks[xid].parents:
                            if pid==yid:
                                found = True
                            q.append(pid)
        return found
            
    def pruneLeaves(self):
        #print("Pruning leaves")
        out = BlockHandler()
        q = deque()
        for rootIdent in self.roots:
            q.append(rootIdent)
        while(len(q)>0):
            thisIdent = q.popleft()
            if thisIdent not in self.leaves:
                out._addBlock(self.blocks[thisIdent])
                for chIdent in self.family[thisIdent]["children"]:
                    q.append(chIdent)
        return out

    def leafBackAntichain(self):
        #print("Computing antichain")
        temp = copy.deepcopy(self)
        decomposition = []
        vulnIdents = []

        decomposition.append([])
        for lid in temp.leaves:
            decomposition[-1].append(lid)
        vulnIdents = copy.deepcopy(decomposition[-1])
        temp = temp.pruneLeaves()
        while(len(temp.blocks)>0 and len(decomposition) < self.antichainCutoff):
            decomposition.append([])
            for lid in temp.leaves:
                decomposition[-1].append(lid)
            for xid in decomposition[-1]:
                if xid not in vulnIdents:
                    vulnIdents.append(xid)
            temp = temp.pruneLeaves()
        return decomposition, vulnIdents
     
class Test_RoBlock(unittest.TestCase):
    def test_betterTest(self):
        R = BlockHandler()
        self.assertTrue(R.data is None)
        self.assertEqual(len(R.blocks),0)
        self.assertEqual(type(R.blocks),type({}))
        self.assertEqual(len(R.family),0)
        self.assertEqual(type(R.family),type({}))
        self.assertEqual(len(R.invDLL),0)
        self.assertEqual(type(R.invDLL),type({}))
        self.assertEqual(len(R.roots),0)
        self.assertEqual(type(R.leaves),type([]))
        self.assertEqual(len(R.leaves),0)
        self.assertEqual(R.antichainCutoff,600)
        self.assertEqual(type(R.roots),type([]))
        self.assertEqual(len(R.pendingVotes),0)
        self.assertEqual(type(R.pendingVotes),type({}))
        self.assertEqual(len(R.votes),0)
        self.assertEqual(type(R.votes),type({}))

        gen = Block() # genesis block
        self.assertTrue(gen.data is None)
        self.assertEqual(gen.parents,[])
        msg = str(0) + str(None) + str([])
        self.assertEqual(gen.ident, hash(msg))

        block0 = gen
        block1 = Block(parentsIn=[block0.ident], dataIn={"timestamp":time.time(), "txns":"pair of zircon encrusted tweezers"})
        block2 = Block(parentsIn=[block1.ident], dataIn={"timestamp":time.time(), "txns":"watch out for that yellow snow"})
        block3 = Block(parentsIn=[block1.ident], dataIn={"timestamp":time.time(), "txns":"he had the stank foot"})
        block4 = Block(parentsIn=[block2.ident, block3.ident], dataIn={"timestamp":time.time(), "txns":"come here fido"})
        block5 = Block(parentsIn=[block3.ident], dataIn={"timestamp":time.time(), "txns":"applied rotation on her sugar plum"})
        block6 = Block(parentsIn=[block5.ident], dataIn={"timestamp":time.time(), "txns":"listen to frank zappa for the love of all that is good"})
        R._addBlock(block0)
        self.assertTrue(block0.ident in R.leaves)
        self.assertTrue(block0.ident in R.roots)        

        R._addBlock(block1)
        self.assertTrue(block1.ident in R.leaves and block0.ident not in R.leaves)
        R._addBlock(block2)
        self.assertTrue(block2.ident in R.leaves and block1.ident not in R.leaves)
        R._addBlock(block3)
        self.assertTrue(block3.ident in R.leaves and block2.ident in R.leaves and block1.ident not in R.leaves)

        R._addBlock(block4)
        self.assertTrue(block4.ident in R.leaves and block3.ident not in R.leaves and block2.ident not in R.leaves)

        R._addBlock(block5)
        self.assertTrue(block4.ident in R.leaves and block5.ident in R.leaves and block3.ident not in R.leaves)

        R._addBlock(block6)
        self.assertTrue(block4.ident in R.leaves and block6.ident in R.leaves and block5.ident not in R.leaves)
        
        self.assertEqual(len(R.blocks), 7)
        self.assertEqual(len(R.family), 7)
        self.assertEqual(len(R.invDLL), 0)
        self.assertEqual(len(R.roots), 1)
        self.assertEqual(len(R.leaves),2)
        self.assertEqual(R.antichainCutoff, 600)
        self.assertEqual(len(R.pendingVotes),0)
        self.assertEqual(len(R.votes),0)

        self.assertTrue(    R._hasAncestor(block6.ident, block0.ident) and not R._hasAncestor(block0.ident, block6.ident))
        self.assertTrue(    R._hasAncestor(block5.ident, block0.ident) and not R._hasAncestor(block0.ident, block5.ident))
        self.assertTrue(    R._hasAncestor(block4.ident, block0.ident) and not R._hasAncestor(block0.ident, block4.ident))
        self.assertTrue(    R._hasAncestor(block3.ident, block0.ident) and not R._hasAncestor(block0.ident, block3.ident))
        self.assertTrue(    R._hasAncestor(block2.ident, block0.ident) and not R._hasAncestor(block0.ident, block2.ident))
        self.assertTrue(    R._hasAncestor(block1.ident, block0.ident) and not R._hasAncestor(block0.ident, block1.ident))

        self.assertTrue(    R._hasAncestor(block6.ident, block1.ident) and not R._hasAncestor(block1.ident, block6.ident))
        self.assertTrue(    R._hasAncestor(block5.ident, block1.ident) and not R._hasAncestor(block1.ident, block5.ident))
        self.assertTrue(    R._hasAncestor(block4.ident, block1.ident) and not R._hasAncestor(block1.ident, block4.ident))
        self.assertTrue(    R._hasAncestor(block3.ident, block1.ident) and not R._hasAncestor(block1.ident, block3.ident))
        self.assertTrue(    R._hasAncestor(block2.ident, block1.ident) and not R._hasAncestor(block1.ident, block2.ident))
        self.assertTrue(not R._hasAncestor(block0.ident, block1.ident) and     R._hasAncestor(block1.ident, block0.ident))

        self.assertTrue(not R._hasAncestor(block6.ident, block2.ident) and not R._hasAncestor(block2.ident, block6.ident))
        self.assertTrue(not R._hasAncestor(block5.ident, block2.ident) and not R._hasAncestor(block2.ident, block5.ident))
        self.assertTrue(    R._hasAncestor(block4.ident, block2.ident) and not R._hasAncestor(block2.ident, block4.ident))
        self.assertTrue(not R._hasAncestor(block3.ident, block2.ident) and not R._hasAncestor(block2.ident, block3.ident))
        self.assertTrue(not R._hasAncestor(block1.ident, block2.ident) and     R._hasAncestor(block2.ident, block1.ident))
        self.assertTrue(not R._hasAncestor(block0.ident, block2.ident) and     R._hasAncestor(block2.ident, block0.ident))

        self.assertTrue(    R._hasAncestor(block6.ident, block3.ident) and not R._hasAncestor(block3.ident, block6.ident))
        self.assertTrue(    R._hasAncestor(block5.ident, block3.ident) and not R._hasAncestor(block3.ident, block5.ident))
        self.assertTrue(    R._hasAncestor(block4.ident, block3.ident) and not R._hasAncestor(block3.ident, block4.ident))
        self.assertTrue(not R._hasAncestor(block2.ident, block3.ident) and not R._hasAncestor(block3.ident, block2.ident))
        self.assertTrue(not R._hasAncestor(block1.ident, block3.ident) and     R._hasAncestor(block3.ident, block1.ident))
        self.assertTrue(not R._hasAncestor(block0.ident, block3.ident) and     R._hasAncestor(block3.ident, block0.ident))

        self.assertTrue(not R._hasAncestor(block6.ident, block4.ident) and not R._hasAncestor(block4.ident, block6.ident))
        self.assertTrue(not R._hasAncestor(block5.ident, block4.ident) and not R._hasAncestor(block4.ident, block5.ident))
        self.assertTrue(not R._hasAncestor(block3.ident, block4.ident) and     R._hasAncestor(block4.ident, block3.ident))
        self.assertTrue(not R._hasAncestor(block2.ident, block4.ident) and     R._hasAncestor(block4.ident, block2.ident))
        self.assertTrue(not R._hasAncestor(block1.ident, block4.ident) and     R._hasAncestor(block4.ident, block1.ident))
        self.assertTrue(not R._hasAncestor(block0.ident, block4.ident) and     R._hasAncestor(block4.ident, block0.ident))

        self.assertTrue(    R._hasAncestor(block6.ident, block5.ident) and not R._hasAncestor(block5.ident, block6.ident))
        self.assertTrue(not R._hasAncestor(block4.ident, block5.ident) and not R._hasAncestor(block5.ident, block4.ident))
        self.assertTrue(not R._hasAncestor(block3.ident, block5.ident) and     R._hasAncestor(block5.ident, block3.ident))
        self.assertTrue(not R._hasAncestor(block2.ident, block5.ident) and not R._hasAncestor(block5.ident, block2.ident))
        self.assertTrue(not R._hasAncestor(block1.ident, block5.ident) and     R._hasAncestor(block5.ident, block1.ident))
        self.assertTrue(not R._hasAncestor(block0.ident, block5.ident) and     R._hasAncestor(block5.ident, block0.ident))

        self.assertTrue(not R._hasAncestor(block5.ident, block6.ident) and     R._hasAncestor(block6.ident, block5.ident))
        self.assertTrue(not R._hasAncestor(block4.ident, block6.ident) and not R._hasAncestor(block6.ident, block4.ident))
        self.assertTrue(not R._hasAncestor(block3.ident, block6.ident) and     R._hasAncestor(block6.ident, block3.ident))
        self.assertTrue(not R._hasAncestor(block2.ident, block6.ident) and not R._hasAncestor(block6.ident, block2.ident))
        self.assertTrue(not R._hasAncestor(block1.ident, block6.ident) and     R._hasAncestor(block6.ident, block1.ident))
        self.assertTrue(not R._hasAncestor(block0.ident, block6.ident) and     R._hasAncestor(block6.ident, block0.ident))
        
        R = R.pruneLeaves()

        self.assertEqual(len(R.blocks), 5)
        self.assertEqual(len(R.family), 5)
        self.assertEqual(len(R.invDLL), 0)
        self.assertEqual(len(R.roots), 1)
        self.assertEqual(len(R.leaves),2)
        self.assertEqual(R.antichainCutoff, 600)
        self.assertEqual(len(R.pendingVotes),0)
        self.assertEqual(len(R.votes),0)

        self.assertTrue(    R._hasAncestor(block5.ident, block0.ident) and not R._hasAncestor(block0.ident, block5.ident))
        self.assertTrue(    R._hasAncestor(block3.ident, block0.ident) and not R._hasAncestor(block0.ident, block3.ident))
        self.assertTrue(    R._hasAncestor(block2.ident, block0.ident) and not R._hasAncestor(block0.ident, block2.ident))
        self.assertTrue(    R._hasAncestor(block1.ident, block0.ident) and not R._hasAncestor(block0.ident, block1.ident))

        self.assertTrue(    R._hasAncestor(block5.ident, block1.ident) and not R._hasAncestor(block1.ident, block5.ident))
        self.assertTrue(    R._hasAncestor(block3.ident, block1.ident) and not R._hasAncestor(block1.ident, block3.ident))
        self.assertTrue(    R._hasAncestor(block2.ident, block1.ident) and not R._hasAncestor(block1.ident, block2.ident))
        self.assertTrue(not R._hasAncestor(block0.ident, block1.ident) and     R._hasAncestor(block1.ident, block0.ident))

        self.assertTrue(not R._hasAncestor(block5.ident, block2.ident) and not R._hasAncestor(block2.ident, block5.ident))
        self.assertTrue(not R._hasAncestor(block3.ident, block2.ident) and not R._hasAncestor(block2.ident, block3.ident))
        self.assertTrue(not R._hasAncestor(block1.ident, block2.ident) and     R._hasAncestor(block2.ident, block1.ident))
        self.assertTrue(not R._hasAncestor(block0.ident, block2.ident) and     R._hasAncestor(block2.ident, block0.ident))

        self.assertTrue(    R._hasAncestor(block5.ident, block3.ident) and not R._hasAncestor(block3.ident, block5.ident))
        self.assertTrue(not R._hasAncestor(block2.ident, block3.ident) and not R._hasAncestor(block3.ident, block2.ident))
        self.assertTrue(not R._hasAncestor(block1.ident, block3.ident) and     R._hasAncestor(block3.ident, block1.ident))
        self.assertTrue(not R._hasAncestor(block0.ident, block3.ident) and     R._hasAncestor(block3.ident, block0.ident))

        self.assertTrue(not R._hasAncestor(block3.ident, block5.ident) and     R._hasAncestor(block5.ident, block3.ident))
        self.assertTrue(not R._hasAncestor(block2.ident, block5.ident) and not R._hasAncestor(block5.ident, block2.ident))
        self.assertTrue(not R._hasAncestor(block1.ident, block5.ident) and     R._hasAncestor(block5.ident, block1.ident))
        self.assertTrue(not R._hasAncestor(block0.ident, block5.ident) and     R._hasAncestor(block5.ident, block0.ident))

        
        ## Formal unit tests for leafBackAntichain() to follow: visual inspection reveals this does what it says on the tin.
        #R.vote()
        #print(R.votes)

    def test_big_bertha(self):
        R = BlockHandler()
        gen = Block() # genesis block
        msg = str(0) + str(None) + str([])
        block0 = gen
        block1 = Block(parentsIn=[block0.ident], dataIn={"timestamp":time.time(), "txns":"pair of zircon encrusted tweezers"})
        block2 = Block(parentsIn=[block1.ident], dataIn={"timestamp":time.time(), "txns":"watch out for that yellow snow"})
        block3 = Block(parentsIn=[block1.ident], dataIn={"timestamp":time.time(), "txns":"he had the stank foot"})
        block4 = Block(parentsIn=[block2.ident, block3.ident], dataIn={"timestamp":time.time(), "txns":"come here fido"})
        block5 = Block(parentsIn=[block3.ident], dataIn={"timestamp":time.time(), "txns":"applied rotation on her sugar plum"})
        block6 = Block(parentsIn=[block5.ident], dataIn={"timestamp":time.time(), "txns":"listen to frank zappa for the love of all that is good"})
        R._addBlock(block0)
        R._addBlock(block1)
        R._addBlock(block2)
        R._addBlock(block3)
        R._addBlock(block4)
        R._addBlock(block5)
        R._addBlock(block6)
        
        # Testing voteFor
        # Verify all roots have children
        for rid in R.roots:
            self.assertFalse(len(R.family[rid]["children"])==0)

        # Verify that all children of all roots have children and collect grandchildren idents
        gc = []
        for rid in R.roots:
            for cid in R.family[rid]["children"]:
                self.assertFalse(len(R.family[cid]["children"]) == 0)
                gc = gc + R.family[cid]["children"]

        # Pick a random grandchild of the root.
        gcid = random.choice(gc)
        
        # Pick a random block with gcid in its past
        vid = random.choice(list(R.blocks.keys()))
        while(not R._hasAncestor(vid, gcid)):
            vid = random.choice(list(R.blocks.keys()))

        # Pick a random pair of blocks for gcid and vid to vote on.    
        xid = random.choice(list(R.blocks.keys()))     
        yid = random.choice(list(R.blocks.keys()))     
        
        # Have vid cast vote that xid < yid
        R.voteFor((vid,xid,yid),{})
        # Verify that R.votes has correct entries
        self.assertEqual(R.votes[(vid,xid,yid)], 1)
        self.assertEqual(R.votes[(vid,yid,xid)],-1)

        # Check that for each ancestor of vid, that they received an appropriate pending vote        
        q = deque()
        for pid in R.blocks[vid].parents:
            if pid in R.vids:
                q.append(pid)
        while(len(q)>0):
            wid = q.popleft()
            self.assertEqual(R.pendingVotes[(wid,xid,yid)],1)
            for pid in R.blocks[wid].parents:
                if pid in R.vids:
                    q.append(pid)
            
        # Now we are going to mess around with how voting at gcid interacts with the above.
        # First, we let gcid cast a vote that xid < yid and check that it propagates appropriately as above.
        R.voteFor((gcid,xid,yid),{})
        self.assertEqual(R.votes[(gcid,xid,yid)],1)
        self.assertEqual(R.votes[(gcid,yid,xid)],-1)
        for pid in R.blocks[vid].parents:
            if pid in R.vids:
                q.append(gpid)
        while(len(q)>0):
            wid = q.popleft()
            self.assertEqual(R.pendingVotes[(wid,xid,yid)],2)
            self.assertEqual(R.pendingVotes[(wid,yid,xid)],-2)
            for pid in R.blocks[wid].parents:
                if pid in R.vids:
                    q.append(pid)
        # Now we are going to have gcid cast the opposite vote. this should change what is stored in R.votes
        # but also change pending votes below gcid
        R.voteFor((gcid,yid,xid),{})
        self.assertEqual(R.votes[(gcid,xid,yid)],-1)
        self.assertEqual(R.votes[(gcid,yid,xid)],1)
        for pid in R.blocks[vid].parents:
            if pid in R.vids:
                q.append(gpid)
        while(len(q)>0):
            wid = q.popleft()
            self.assertEqual(R.pendingVotes[(wid,xid,yid)],0)
            self.assertEqual(R.pendingVotes[(wid,yid,yid)],0)
            for pid in R.blocks[wid].parents:
                if pid in R.vids:
                    q.append(pid)
        # Do again, now pending votes should be negative
        R.voteFor((gcid,yid,xid),{})
        self.assertEqual(R.votes[(gcid,xid,yid)],-1)
        self.assertEqual(R.votes[(gcid,yid,xid)],1)
        for pid in R.blocks[vid].parents:
            if pid in R.vids:
                q.append(gpid)
        while(len(q)>0):
            wid = q.popleft()
            self.assertEqual(R.pendingVotes[(wid,xid,yid)],-1)
            self.assertEqual(R.pendingVotes[(wid,yid,yid)],-1)
            for pid in R.blocks[wid].parents:
                if pid in R.vids:
                    q.append(pid)





                
        #R.vote()
        #print(R.votes)


        
suite = unittest.TestLoader().loadTestsFromTestCase(Test_RoBlock)
unittest.TextTestRunner(verbosity=1).run(suite)
