import typing
import src.utils as utils

def orientation(pivot, q, r) -> str:
    """Find orientation from q to r about a pivot point.
        returns: 'cw', 'ccw', or 'col' (colinear)
    """
    val = (q[1] - pivot[1]) * (r[0] - q[0]) - (q[0] - pivot[0]) * (r[1] - q[1])
    if val == 0:
        return 'col'
    else:
        return 'cw' if val > 0 else 'ccw'

def compute(
        points: typing.List[typing.Tuple[float, float]],
        include_colinear_edge_points=False
) -> typing.List[typing.Tuple[float, float]]:

    if len(points) < 3:
        return list(points)

    res = []
    leftmost_idx = min((idx for idx in range(len(points))), key=lambda _idx: points[_idx][0])
    pivot_idx = leftmost_idx

    while True:
        res.append(pivot_idx)  # add current pivot to hull
        next_idx = (pivot_idx + 1) % len(points)

        # find next pivot
        for i in range(len(points)):
            ori = orientation(points[pivot_idx], points[i], points[next_idx])
            if ori == 'ccw':
                next_idx = i
            elif ori == 'col':  # they're co-linear, can choose whether to take point or not
                pivot_to_i_dist2 = utils.dist2(points[pivot_idx], points[i])
                pivot_to_next_dist2 = utils.dist2(points[pivot_idx], points[next_idx])
                if pivot_to_i_dist2 > pivot_to_next_dist2:
                    # Take farther point.
                    next_idx = i

        pivot_idx = next_idx  # continue from new pivot

        # if we've wrapped back around to the original pivot, we've completed the hull.
        if (pivot_idx == leftmost_idx):
            break

    res = [points[idx] for idx in res]

    if include_colinear_edge_points:
        res = _insert_colinear_edge_points(res, points)

    return res

def _insert_colinear_edge_points(hull, points):
    in_hull_already = set(hull)
    res = []
    for i in range(len(hull)):
        e1 = hull[i]
        e2 = hull[(i + 1) % len(hull)]

        colinears = []
        for p in points:
            if p in in_hull_already:
                continue
            elif utils.dist_from_point_to_line(p, e1, e2, segment=True) < 0.0001:
                colinears.append(p)

        colinears.sort(key=lambda x: utils.dist(e1, x))

        res.append(e1)
        res.extend(colinears)
        in_hull_already.update(colinears)

    return res


