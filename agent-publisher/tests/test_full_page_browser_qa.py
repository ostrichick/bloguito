"""Synthetic negative tests for supplemental Q1 full-page/CTA receipts."""
import copy
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "full_page_verifier", REPO / "scripts/verify_full_page_browser_qa.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SHA = "a" * 64
URL = "https://lifeinfo24.org/2026-10-test-post/"
CTA = "https://rsvn.science.go.kr/detail?id=100"


def fixture(root: Path):
    screens = []
    for width, height in ((390, 844), (1280, 900)):
        root.joinpath("segments").mkdir(exist_ok=True)
        parts = []
        for i, top in enumerate((0, height-100, 2*height-200)):
            name=f"segments/{width}-{i}.png"
            path=root/name
            Image.new("RGB", (width, height), "white").save(path)
            parts.append({"index": i, "filename": name,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "scrollY":top,"viewportWidth":width,
                          "viewportHeight":height,"observedPostId":641})
        zoom_name=f"segments/{width}-zoom.png"
        path=root/zoom_name
        Image.new("RGB", (width, height), "white").save(path)
        basic={"postId":641,"url":URL,"innerWidth":width,
               "scrollHeight":3*height-200,"scrollWidth":width,
               "clientWidth":width}
        screens.append({
            "viewport":{"width":width,"height":height},"initial":basic,"final":basic,
            "total_height":3*height-200,"full_page_covered":True,
            "segments":parts,
            "zoom":{"method":"Emulation.setPageScaleFactor","requested":2,
                    "observedVisualScale":2,"observedVisualWidth":width/2,
                    "observedLayoutWidth":width,"screenshot":zoom_name,
                    "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                    "isNativeChromeMenuZoom":False,"isCssHalfWidthTrick":False}})
    evidence={"postId":641,"site":"https://lifeinfo24.org/",
              "originalContentSha256":SHA,"screens":screens}
    cta={"source_post_id":641,"main_page_preserved":True,"new_tab_observed":True,
         "click":"CDP Input.dispatchMouseEvent mousePressed+mouseReleased",
         "cta":{"href":CTA,"target":"_blank","tag":"A","method":None,
                "centerAnchorHref":CTA},
         "targets":[{"id":"new-page","type":"page","url":CTA}],
         "document_responses":[{"targetId":"new-page","url":CTA,"status":200,"mimeType":"text/html"}]}
    return evidence,cta


class FullPageVerifierTests(unittest.TestCase):
    def test_full_page_and_new_tab_document_verified_without_native_zoom_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            data, cta=fixture(root)
            report=module.verify_full_page(data,root,post_id=641,content_sha=SHA)
            self.assertEqual("supplemental_full_page_verified",report["status"])
            self.assertEqual("not_verified",report["native_browser_menu_zoom"])
            self.assertEqual("observed_new_tab_document_200",
                             module.verify_blank_cta(cta,post_id=641)["status"])

    def test_missing_scroll_middle_section_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data,_=fixture(root)
            data["screens"][0]["segments"][1]["scrollY"]=1800
            with self.assertRaisesRegex(ValueError,"segment_gap_or_identity"):
                module.verify_full_page(data,root,post_id=641,content_sha=SHA)

    def test_screenshot_replacement_and_wrong_post_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data,_=fixture(root)
            data["screens"][0]["segments"][0]["observedPostId"]=999
            with self.assertRaisesRegex(ValueError,"segment_gap_or_identity"):
                module.verify_full_page(data,root,post_id=641,content_sha=SHA)
            data["screens"][0]["segments"][0]["observedPostId"]=641
            (root/data["screens"][0]["segments"][0]["filename"]).write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError,"png_sha_mismatch"):
                module.verify_full_page(data,root,post_id=641,content_sha=SHA)

    def test_half_viewport_cannot_be_presented_as_zoom(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data,_=fixture(root)
            data["screens"][1]["zoom"]["method"]="half_css_viewport"
            with self.assertRaisesRegex(ValueError,"zoom_2x_unverified"):
                module.verify_full_page(data,root,post_id=641,content_sha=SHA)

    def test_cta_missing_http_and_fake_target_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            _,cta=fixture(Path(directory))
            cta["document_responses"][0]["status"]=403
            with self.assertRaisesRegex(ValueError,"http_200_unverified"):
                module.verify_blank_cta(cta,post_id=641)
            cta["document_responses"][0]["status"]=200
            cta["targets"][0]["url"]="about:blank"
            with self.assertRaisesRegex(ValueError,"destination_unverified"):
                module.verify_blank_cta(cta,post_id=641)


if __name__=="__main__":
    unittest.main()
