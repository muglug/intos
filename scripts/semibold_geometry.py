"""Contour interpolation for the hand-edited, non-compatible upright masters."""
import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.misc.bezierTools import splitCubicAtT


class CubicContours(BasePen):
    def __init__(self, glyph_set=None):
        super().__init__(glyph_set)
        self.contours = []
        self.segments = []

    def _moveTo(self, point):
        self.start = np.array(point, dtype=float)
        self.segments = []

    def _lineTo(self, point):
        a = np.array(self._getCurrentPoint(), dtype=float)
        b = np.array(point, dtype=float)
        if np.linalg.norm(b-a) > 1e-8:
            self.segments.append(np.array([a, a+(b-a)/3, a+2*(b-a)/3, b]))

    def _curveToOne(self, a, b, c):
        self.segments.append(np.array([self._getCurrentPoint(), a, b, c], dtype=float))

    def _qCurveToOne(self, control, end):
        a = np.array(self._getCurrentPoint(), dtype=float)
        b, c = np.array(control), np.array(end)
        self.segments.append(np.array([a, a+2*(b-a)/3, c+2*(b-c)/3, c]))

    def _closePath(self):
        self._lineTo(self.start)
        if self.segments:
            self.contours.append(np.array(self.segments))
        self.segments = []

    def _endPath(self):
        raise ValueError('Open contour cannot be interpolated as a filled outline')


def sample(segment, t):
    t = np.asarray(t)[:, None]
    return ((1-t)**3*segment[0] + 3*(1-t)**2*t*segment[1]
            + 3*(1-t)*t*t*segment[2] + t**3*segment[3])


def descriptor(contour):
    points = np.concatenate([sample(s, np.linspace(0, 1, 12)) for s in contour])
    area = np.sum(points[:, 0]*np.roll(points[:, 1], -1)
                  - points[:, 1]*np.roll(points[:, 0], -1))/2
    return np.r_[points.min(0), points.max(0)], area


def corners(contour):
    result = []
    for i, segment in enumerate(contour):
        incoming = contour[i-1][3]-contour[i-1][2]
        outgoing = segment[1]-segment[0]
        den = np.linalg.norm(incoming)*np.linalg.norm(outgoing)
        if den and np.dot(incoming, outgoing)/den < .985:
            result.append(i)
    return result


def section(contour, start, end):
    if end <= start:
        end += len(contour)
    return np.array([contour[i % len(contour)] for i in range(start, end)])


def length_data(contour):
    ts = np.linspace(0, 1, 65)
    tables = [np.r_[0, np.cumsum(np.linalg.norm(np.diff(sample(s, ts), axis=0), axis=1))]
              for s in contour]
    bounds = np.r_[0, np.cumsum([t[-1] for t in tables])]
    return ts, tables, bounds/bounds[-1], bounds[-1]


def subcurve(segment, start, end):
    if start < 1e-9 and end > 1-1e-9:
        return segment
    cuts = [t for t in [start, end] if 1e-9 < t < 1-1e-9]
    parts = splitCubicAtT(*[tuple(p) for p in segment], *cuts)
    return np.array(parts[1 if start > 1e-9 else 0])


def interpolate_section(a, b, weight):
    data = [length_data(c) for c in [a, b]]
    knots = sorted(set(round(float(v), 10) for d in data for v in d[2]))
    result = []
    for low, high in zip(knots, knots[1:]):
        if high-low < 1e-8:
            continue
        parts = []
        for contour, (ts, tables, bounds, total) in zip([a, b], data):
            i = min(len(contour)-1, np.searchsorted(bounds, (low+high)/2)-1)
            t0, t1 = [np.interp((v-bounds[i])*total, tables[i], ts) for v in [low, high]]
            parts.append(subcurve(contour[i], t0, t1))
        result.append((1-weight)*parts[0]+weight*parts[1])
    return result


def interpolate_contour(a, b, weight):
    ca, cb = corners(a), corners(b)
    bounds_a, _ = descriptor(a); bounds_b, _ = descriptor(b)
    normal = lambda p, bounds: (p-bounds[:2])/np.maximum(bounds[2:]-bounds[:2], 1)
    if ca and len(ca) == len(cb):
        costs = []
        for offset in range(len(cb)):
            candidate = cb[offset:]+cb[:offset]
            costs.append(sum(np.linalg.norm(normal(a[i, 0], bounds_a)-normal(b[j, 0], bounds_b))**2
                             for i, j in zip(ca, candidate)))
        offset = int(np.argmin(costs)); cb = cb[offset:]+cb[:offset]
        output = []
        for k, (i, j) in enumerate(zip(ca, cb)):
            output.extend(interpolate_section(section(a, i, ca[(k+1) % len(ca)]),
                                              section(b, j, cb[(k+1) % len(cb)]), weight))
        return np.array(output)
    # Smooth loops use a corresponding leftmost on-curve start.
    def start(contour, bounds):
        p = normal(contour[:, 0], bounds)
        return int(np.argmin(p[:, 0]+.01*abs(p[:, 1]-.5)))
    a = np.roll(a, -start(a, bounds_a), axis=0)
    b = np.roll(b, -start(b, bounds_b), axis=0)
    return np.array(interpolate_section(a, b, weight))


def interpolate_outlines(a, b, weight):
    # Extra contours can emerge/disappear between masters (for example, a
    # crossbar closes a counter). Interpolate those toward a collapsed contour.
    def collapsed(contour):
        box, _ = descriptor(contour)
        center = (box[:2]+box[2:])/2
        return center+(contour-center)*1e-7
    unused = set(range(len(b))); result = []
    for contour in a:
        bounds, area = descriptor(contour)
        options = []
        for i in unused:
            other_bounds, other_area = descriptor(b[i])
            if area*other_area > 0:
                cost = np.linalg.norm(bounds-other_bounds) + abs(abs(area)**.5-abs(other_area)**.5)
                options.append((cost, i))
        if options:
            _, i = min(options); unused.remove(i); other = b[i]
        else:
            other = collapsed(contour)
        result.append(interpolate_contour(contour, other, weight))
    for i in sorted(unused):
        result.append(interpolate_contour(collapsed(b[i]), b[i], weight))
    return result


def draw_contours(contours, pen):
    for contour in contours:
        pen.moveTo(tuple(contour[0, 0]))
        for segment in contour:
            pen.curveTo(*[tuple(p) for p in segment[1:]])
        pen.closePath()
