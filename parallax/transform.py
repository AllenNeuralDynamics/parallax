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
        self.params = {}
        self.rmse = None
        self.convergence = None

    def compute_from_correspondence(self, from_points, to_points):
        raise NotImplementedError

    def compute_rmse(self):
        if all(a is not None for a in (self.from_points, self.to_points)):
            npts = self.from_points.shape[0]
            delta = np.zeros((npts,3), dtype=np.float32)
            for i in range(npts):
                gt = self.to_points[i,:]
                tt = self.map(self.from_points[i,:])
                delta[i,:] = np.linalg.norm(tt - gt)
            self.rmse = np.sqrt(np.mean(delta*delta))

    def compute_convergence(self, cls_tx):
        """
        Convergence is defined as the RMS difference between the points projected
        by the transform, and the points projected by each of the N transforms
        created by removing one of the N correspondence points.
        """
        if all(a is not None for a in (self.from_points, self.to_points)):
            npts = self.from_points.shape[0]
            delta = np.zeros((npts,npts,3), dtype=np.float32)
            for ir in range(npts):  # removed index
                indices = np.concatenate((np.arange(ir), np.arange(ir+1,npts)))
                txm1 = cls_tx('dummy', 'dummy', 'dummy')
                txm1.compute_from_correspondence(self.from_points[indices,:],
                                                self.to_points[indices,:], convergence=False)
                for j in range(npts):
                    p = self.map(self.from_points[j,:])
                    pm1 = txm1.map(self.from_points[j,:])
                    delta[ir,j,:] = p - pm1
            self.convergence = np.sqrt(np.mean(delta*delta))
        
    def compute_variance(self, cls_tx):
        raise NotImplementedError
        
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

class TransformRT(Transform):

    """
    Rigid body transform (rotation and translation) plus metadata
    Implemented using coorx
    """

    def __init__(self, name, from_cs, to_cs):
        Transform.__init__(self, name, from_cs, to_cs)
        self.tx = coorx.RT3DTransform(from_cs=from_cs, to_cs=to_cs)

    def compute_from_correspondence(self, from_points, to_points, convergence=True):
        self.from_points = from_points
        self.to_points = to_points
        self.tx.set_mapping(from_points, to_points)
        self.compute_rmse()
        if convergence:
            self.compute_convergence()

    def compute_convergence(self):
        Transform.compute_convergence(self, TransformSRT)

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

class TransformSRT(Transform):

    """
    Rigid body transform (scaling, rotation, and translation) plus metadata
    Implemented using coorx
    """

    def __init__(self, name, from_cs, to_cs):
        Transform.__init__(self, name, from_cs, to_cs)
        self.tx = coorx.SRT3DTransform(from_cs=from_cs, to_cs=to_cs)

    def compute_from_correspondence(self, from_points, to_points, convergence=True):
        self.from_points = from_points
        self.to_points = to_points
        self.tx.set_mapping(from_points, to_points)
        self.compute_rmse()
        if convergence:
            self.compute_convergence()

    def compute_convergence(self):
        Transform.compute_convergence(self, TransformSRT)

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

