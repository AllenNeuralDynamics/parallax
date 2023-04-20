import coorx

class Transform:

    """
    Rigid body transform (rotation and translation) plus metadata
    """

    def __init__(self, name, from_cs, to_cs):
        self.name = name
        self.from_cs = from_cs
        self.to_cs = to_cs
        self.tx = coorx.SRT3DTransform(from_cs=from_cs, to_cs=to_cs)

    def compute_from_correspondence(self, from_points, to_points):
        self.tx.set_mapping(from_points, to_points)
        
    def compute_from_composition(self, transforms):
        txs = [transform.tx for transform in transforms]
        self.tx = coorx.CompositeTransform(txs)

    def map(self, p):
        return self.tx.map(p)

    def inverse_map(self, p):
        #return self.tx.inverse.map(p)
        return self.tx.imap(p)
