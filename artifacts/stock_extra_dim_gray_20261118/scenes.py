"""Render the three SDR comparison pages; no device I/O or setting changes."""
import argparse
import base64

CODES = (255, 191, 133)
PLAN = (
    ('Woff1', 255, False), ('Won1', 255, True), ('WonSham', 255, True),
    ('G191', 191, False), ('Won2', 255, True), ('G133', 133, False),
    ('Won3', 255, True), ('Woff2', 255, False),
)


def gray_candidates(coefficient=0.522):
    """Hypotheses, not a photometric match. Use standard sRGB encoding."""
    if not 0 <= coefficient <= 1:
        raise ValueError("coefficient out of range")
    srgb = 12.92 * coefficient if coefficient <= 0.0031308 else 1.055 * coefficient ** (1 / 2.4) - 0.055
    return round(255 * srgb), round(255 * coefficient)


def page(code):
    if code not in CODES:
        raise ValueError("unknown trial code")
    return ('<!doctype html><meta charset=utf-8><meta name=viewport '
            'content="width=device-width,initial-scale=1"><style>html,body{margin:0;'
            'height:100%;width:100%;overflow:hidden;background:rgb('
            + ','.join([str(code)] * 3) + ')}</style><body></body>')


def data_url(code):
    return 'data:text/html;base64,' + base64.b64encode(page(code).encode()).decode()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('code', type=int, choices=CODES)
    parser.add_argument('--data-url', action='store_true')
    args = parser.parse_args()
    print(data_url(args.code) if args.data_url else page(args.code))
