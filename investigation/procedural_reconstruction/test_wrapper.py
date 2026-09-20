class MockMB:
    def box(self, a, t, n, u1, u2, z1, z2, w1, w2):
        print(f"box: z1={z1}, z2={z2}")
    def beam(self, a, b, radius=0.018):
        print("beam")

class ZOffsetMeshBuilder:
    def __init__(self, builder, z_offset):
        self._builder = builder
        self._z_offset = z_offset

    def box(self, a, t, n, u1, u2, z1, z2, w1, w2, *args, **kwargs):
        return self._builder.box(a, t, n, u1, u2, z1 + self._z_offset, z2 + self._z_offset, w1, w2, *args, **kwargs)
        
    def __getattr__(self, name):
        return getattr(self._builder, name)

mb = ZOffsetMeshBuilder(MockMB(), 4.0)
mb.box(None, None, None, 0, 10, 0, 16, 0, 0)
mb.beam(None, None)
