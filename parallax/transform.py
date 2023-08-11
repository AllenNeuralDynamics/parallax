import coorx
import numpy as np
from scipy.optimize import leastsq

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
        self.convergence = None
        self.variance = None

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

    def compute_convergence(self):
        """
        Convergence is defined as the RMS difference between the points projected
        by the transform, and the points projected by each of the N transforms
        created by removing one of the N correspondence points.
        """
        if all(a is not None for a in (self.from_points, self.to_points)):
            npts = self.from_points.shape[0]
            delta = np.zeros((npts,npts,3), dtype=np.float32)
            cls_tx = type(self)
            for ir in range(npts):  # removed index
                indices = np.concatenate((np.arange(ir), np.arange(ir+1,npts)))
                txm1 = cls_tx('', '', '')
                txm1.compute_from_correspondence(self.from_points[indices,:],
                                                self.to_points[indices,:],
                                                convergence=False, variance=False)
                for j in range(npts):
                    p = self.map(self.from_points[j,:])
                    pm1 = txm1.map(self.from_points[j,:])
                    delta[ir,j,:] = p - pm1
            self.convergence = np.sqrt(np.mean(delta*delta))
        
    def compute_variance(self):
        """
        Variance is defined as the standard deviation of the distribution (size N)
        of M parameter values created by removing each of the N correspondence points.
        """
        if all(a is not None for a in (self.from_points, self.to_points)):
            npts = len(self.from_points)
            m =  len(self.params)
            params_m1 = np.zeros((npts,m), dtype=np.float32)
            cls_tx = type(self)
            for ir in range(npts):  # removed index
                indices = np.concatenate((np.arange(ir), np.arange(ir+1,npts)))
                txm1 = cls_tx('', '', '')
                txm1.compute_from_correspondence(self.from_points[indices,:],
                                                self.to_points[indices,:],
                                                convergence=False, variance=False)
                params_m1[ir,:] = txm1.params
            self.variance = np.std(params_m1, axis=0)
        
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

    def compute_from_correspondence(self, from_points, to_points, convergence=True,
                                    variance=True):
        self.from_points = from_points
        self.to_points = to_points
        self.tx.set_mapping(from_points, to_points)
        self.params = np.zeros(10, dtype=np.float32)
        self.params[0:3] = self.tx._state['offset']
        self.params[3:6] = self.tx._state['scale']
        self.params[6] = self.tx._state['angle']
        self.params[7:10] = self.tx._state['axis']
        self.compute_rmse()
        if convergence:
            self.compute_convergence()
        if variance:
            self.compute_variance()

    def compute_from_composition(self, transforms):
        txs = [transform.tx for transform in transforms]
        self.tx = coorx.CompositeTransform(txs)

    def map(self, p):
        return self.tx.map(p)

    def inverse_map(self, p):
        return self.tx.imap(p)

    def get_inverse(self):
        new_transform = TransformSRT(f"{self.name}-inv", self.to_cs, self.from_cs)
        new_transform.tx = self.tx.inverse
        return new_transform


def _roll(inputMat, g): 
    rollMat = np.array([[1, 0,         0],
               [0, np.cos(g), -np.sin(g)],
               [0, np.sin(g), np.cos(g)]])
    return np.dot(inputMat,rollMat)

def _pitch(inputMat, b):
    pitchMat = np.array([[np.cos(b), 0, np.sin(b)],
               [0, 1, 0],
               [-np.sin(b), 0, np.cos(b)]])
    return np.dot(inputMat,pitchMat)

def _yaw(inputMat, a):
    yawMat = np.array([[np.cos(a), -np.sin(a), 0],
               [np.sin(a), np.cos(a), 0],
               [0, 0, 1]])
    return np.dot(inputMat,yawMat)

def _errfunc(x, global_pts, measured_pts):
    rot = _combine_angles(x[2], x[1], x[0])
    ori = np.array([x[3], x[4], x[5]]).T
    M = global_pts.shape[0]
    error_values = np.zeros((M * 3,))
    for i in range(M):
        global_pt = global_pts[i,:].T
        measured_pt = measured_pts[i,:].T - np.array([3,3,3])
        local_pt = np.dot(global_pt + ori, rot)
        error_values[0+i*3:3+i*3] = local_pt - measured_pt
    return error_values

def _combine_angles(x, y, z):
    eye = np.identity(3)
    rot = _roll(_pitch(_yaw(eye,z),y),x)
    return rot

def _extract_angles(mat):
    x = np.arctan2(mat[2,1],mat[2,2])
    y = np.arctan2(-mat[2,0], np.sqrt(pow(mat[2,1],2)+ pow(mat[2,2],2)))
    z = np.arctan2(mat[1,0],mat[0,0])
    return np.array([x, y, z], dtype=np.float32)

class TransformRT(Transform):

    """
    Rigid body transform (rotation and translation, no scaling) plus metadata
    Implemented using coorx
    """

    def __init__(self, name, from_cs, to_cs):
        Transform.__init__(self, name, from_cs, to_cs)
        self.tx = coorx.RT3DTransform(from_cs=from_cs, to_cs=to_cs)

    def compute_from_correspondence(self, from_points, to_points,
                                    convergence=True, variance=True):
        self.from_points = from_points
        self.to_points = to_points
        self.tx.set_mapping(from_points, to_points)
        self.compute_rmse()
        if convergence:
            self.compute_convergence()
        if variance:
            self.compute_variance()

    def compute_convergence(self):
        Transform.compute_convergence(self, TransformSRT)

    def compute_variance(self):
        Transform.compute_variance(self, TransformSRT)

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

class TransformNP(Transform):

    """
    Rigid body transform (rotation and translation, no scaling) plus metadata
    Based on rotations.py
        -> github.com/AllenInstitute/neuropixels_protocol_resources/tree/main/Notebooks
    """

    def __init__(self, name, from_cs, to_cs):
        Transform.__init__(self, name, from_cs, to_cs)

    def compute_from_correspondence(self, from_points, to_points, convergence=True,
                                    variance=True):

        self.from_points = from_points
        self.to_points = to_points

        x0 = np.array([0,0,0,0,0,0])
        rz, ry, rx, x, y, z = leastsq(_errfunc, x0, args=(from_points, to_points))[0]
        self.rot = _combine_angles(rx,ry,rz)
        self.ori = np.array([x,y,z], dtype=np.float32)
        self.params = np.array([rx,ry,rz,x,y,z], dtype=np.float32)
        self.compute_rmse()
        if convergence:
            self.compute_convergence()
        if variance:
            self.compute_variance()

    def set_from_rot_ori(self, rot, ori):
        self.rot = rot
        self.ori = ori
        self.params = np.zeros(6, dtype=np.float32)
        self.params[:3] = _extract_angles(rot)
        self.params[3:] = ori

    def compute_from_composition(self, transforms):
        rot = np.identity(3)
        ori = np.zeros(3)
        if all(isinstance(t, TransformNP) for t in transforms):
            for t in transforms:
                ori = ori + np.dot(rot, t.ori)
                rot = np.dot(rot, t.rot)
            self.set_from_rot_ori(rot, ori)
        else:
            raise ValueError('transforms must be of type TransformNP')

    def map(self, p):
        return np.dot(p + self.ori, self.rot)

    def inverse_map(self, p):
        return np.dot(self.rot, p) - self.ori

    def get_inverse(self):
        new_transform = TransformNP(f"{self.name}-inv", self.to_cs, self.from_cs)
        new_transform.set_from_rot_ori(self.rot.T, (-1) * np.dot(T, self.rot))
        return new_transform

