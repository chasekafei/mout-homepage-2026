"""Stack a render above the concept image for visual comparison."""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CONCEPT = ROOT / "output/environment-redesign/creation-room-concept-direct-01.png"

render = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".cache/renders/preview_desktop.png"
out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / ".cache/compare.png"
a = Image.open(render).convert("RGB")
b = Image.open(CONCEPT).convert("RGB").resize(a.size, Image.LANCZOS)
sheet = Image.new("RGB", (a.width, a.height * 2 + 8), (255, 255, 255))
sheet.paste(a, (0, 0))
sheet.paste(b, (0, a.height + 8))
sheet.save(out)
print(out)
