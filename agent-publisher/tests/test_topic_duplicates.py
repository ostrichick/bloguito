import unittest
from unittest.mock import patch
from agents.search_intent import duplicate_posts, load_briefs

class DuplicateTests(unittest.TestCase):
    def test_changed_title_same_event(self):
        b={'required_title_terms':['무명전설','수원','앵콜'],'official_urls':[]}
        p={'ID':70,'post_status':'publish','post_title':'2026 무명전설 크리스마스 수원 앙코르 예매'}
        self.assertEqual(duplicate_posts(b,[p]),[p])
        self.assertEqual(duplicate_posts(b,[{**p,'post_title':'무명전설 부산 앵콜'}]),[])
    def test_same_product_and_draft(self):
        b={'required_title_terms':['다른 제목'],'official_urls':['https://example.com/product/1']}
        p={'post_status':'draft','post_content':'<a href="https://example.com/product/1">예매</a>'}
        self.assertEqual(duplicate_posts(b,[p]),[p])
        self.assertEqual(duplicate_posts(b,[{**p,'post_status':'trash'}]),[])
    def test_missing_inventory_blocks(self):
        with patch('agents.search_intent.INVENTORY') as inventory:
            inventory.read_text.side_effect=FileNotFoundError
            self.assertEqual(load_briefs('concert'),[])
