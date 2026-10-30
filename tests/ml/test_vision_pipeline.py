"""ROV vision pipeline on real photos: YOLOv8n objects + distances, Haar/LBPH faces (skips without CV deps)."""

import pathlib

import pytest

cv2 = pytest.importorskip('cv2')
ultralytics = pytest.importorskip('ultralytics')
if not hasattr(cv2, 'face'):
    pytest.skip('opencv-contrib (cv2.face) not installed', allow_module_level=True)

from src.cv.vision.pipeline import CV_DIR, VisionPipeline, estimate_distance  # noqa: E402

ASSETS = pathlib.Path(ultralytics.__file__).parent / 'assets'


@pytest.fixture(scope='module')
def pipe():
    return VisionPipeline.load()


def test_distance_is_pinhole():
    assert estimate_distance('person', 140, 700) == pytest.approx(0.45 * 700 / 140, abs=0.01)
    assert estimate_distance('unicorn', 100, 700) is None and estimate_distance('person', 0, 700) is None


def test_objects_people_and_distances(pipe):
    out, det = pipe.process(cv2.imread(str(ASSETS / 'bus.jpg')))
    labels = [o['label'] for o in det['objects']]
    assert 'bus' in labels and det['persons'] >= 3
    for o in det['objects']:
        assert len(o['box']) == 4 and 0 < o['confidence'] <= 1
        assert o['distance_m'] is None or 0.2 < o['distance_m'] < 50
    assert out.shape[1] == 640 and det['frame_w'] == 640


def test_enrolled_face_is_recognised_and_strangers_are_not(pipe):
    img = sorted((CV_DIR / 'face_recognition' / 'images').glob('Users-3-*.jpg'))[0]
    g = cv2.copyMakeBorder(cv2.imread(str(img), cv2.IMREAD_GRAYSCALE), 50, 50, 50, 50, cv2.BORDER_REPLICATE)
    canvas = cv2.cvtColor(cv2.copyMakeBorder(g, 0, 480 - g.shape[0], 0, 640 - g.shape[1], cv2.BORDER_CONSTANT, value=40),
                          cv2.COLOR_GRAY2BGR)
    _, det = pipe.process(canvas)
    assert [f['name'] for f in det['faces']] == ['Harsh'] and det['faces'][0]['match'] > 0.5
    _, det = pipe.process(cv2.imread(str(ASSETS / 'zidane.jpg')))
    assert det['faces'] and all(f['name'] == 'Unknown' for f in det['faces'])
