import coorx
import numpy as np

class Transform:

    """
    Base case for coordinate transforms
    """

    def __init__(self, name, from_cs, to_cs):
        self.name = name
        self.from_cs = from_cs
        self.to_cs = to_cs
        self.params = None
        self.rmse = None
        self.confidence = None

    def compute_from_correspondence(self, from_points, to_points):
        raise NotImplementedError

    def compute_rmse(self):
        npts = self.from_points.shape[0]
        diffs = np.zeros(npts, dtype=np.float32)
        for i in range(npts):
            gt = self.to_points[i,:]
            tt = self.map(self.from_points[i,:])
            diffs[i] = np.linalg.norm(tt - gt)
        self.rmse = np.mean(diffs)

    def compute_confidence_old(self):
        npts = self.from_points.shape[0]
        self.txm1.set_mapping(self.from_points[:npts-1,:], self.to_points[:npts-1,:])
        self.diffs_txm1 = np.zeros((npts-1,3))
        for i in range(npts-1):
            p = self.map(self.from_points[i,:])
            pm1 = self.txm1.map(self.from_points[i,:])
            self.diffs_txm1[i,:] = p - pm1
        self.confidence = np.mean(np.linalg.norm(self.diffs_txm1, axis=1))
        
    def compute_confidence(self, cls_tx):
        npts = self.from_points.shape[0]
        print('NPTS = ', npts)
        self.diffs_txm1 = np.zeros((npts,npts-1,3), dtype=np.float32)
        for i in range(npts):
            indices = np.concatenate((np.arange(i), np.arange(i+1,npts)))
            txm1 = cls_tx('dummy', 'dummy', 'dummy')
            txm1.compute_from_correspondence(self.from_points[indices,:],
                                            self.to_points[indices,:], confidence=False)
            for j,index in enumerate(indices):
                p = self.map(self.from_points[index,:])
                pm1 = txm1.map(self.from_points[index,:])
                self.diffs_txm1[i,j,:] = p - pm1
        self.confidence = np.mean(np.linalg.norm(self.diffs_txm1, axis=2))
        
    def compute_from_composition(self, transforms):
        raise NotImplementedError

    def map(self, p):
        raise NotImplementedError
        return None

    def inverse_map(self, p):
        raise NotImplementedError
        return None

    def get_inverse(self):
        raise NotImplementedError
        return None

class TransformSRT(Transform):

    """
    Rigid body transform (scaling, rotation, and translation) plus metadata
    Implemented using coorx
    """

    def __init__(self, name, from_cs, to_cs):
        Transform.__init__(self, name, from_cs, to_cs)
        self.tx = coorx.SRT3DTransform(from_cs=from_cs, to_cs=to_cs)

    def compute_from_correspondence(self, from_points, to_points, confidence=True):
        self.from_points = from_points
        self.to_points = to_points
        self.tx.set_mapping(from_points, to_points)
        self.compute_rmse()
        if confidence:
            self.compute_confidence()

    def compute_confidence(self):
        #self.txm1 = coorx.SRT3DTransform(from_cs=self.from_cs, to_cs=self.to_cs)
        #Transform.compute_confidence(self)
        Transform.compute_confidence(self, TransformSRT)

    def compute_from_composition(self, transforms):
        txs = [transform.tx for transform in transforms]
        self.tx = coorx.CompositeTransform(txs)

    def map(self, p):
        return self.tx.map(p)

    def inverse_map(self, p):
        return self.tx.imap(p)

    def get_inverse(self):
        new_transform = Transform(f"{self.name}-inv", self.to_cs, self.from_cs)
        new_transform.tx = self.tx.inverse
        return new_transform

