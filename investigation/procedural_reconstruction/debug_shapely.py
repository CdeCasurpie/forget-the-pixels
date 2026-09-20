from shapely.geometry import Polygon
parcel = Polygon([(0,0), (10,0), (10,20), (0,20)])
p0 = (9.80, 20)
p1 = (9.80, 10)
p2 = (10.0, 10)
p3 = (10.0, 20)
shape = Polygon([p0, p1, p2, p3])
print("Shape area:", shape.area)
print("Intersection area:", shape.intersection(parcel).area)
