import os
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from datetime import timedelta
from django.utils import timezone
from playwright.sync_api import sync_playwright
from admin_panel.models import FAQ, Admin

class FAQPageE2ETest(StaticLiveServerTestCase):
    """
    End-to-end test for the audit log page. Navigates through the login page to the faq page and finally ends at the audit log page where it confirms the dummy log is there and all relevant information is displayed as intended
    """
    @classmethod
    def setUpClass(cls):
        """Set up browser and playwright instance for e2e test"""
        # Fixes async with synchronous issue since django executes synchronously but playwright is asynchronous
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        # starts a browser instance for playwright
        cls.playwright = sync_playwright().start()
        # turn off gui display of browser
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        """Kill resources used for e2e test by playwright"""
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        """Create necessary dummy objects for e2e test of audit logs"""
        # Create a test admin and log entry in the database.
        self.user = Admin.objects.create_user(
            foodbank_email = "evanscott@sandiego.edu",
            username = "evanscott",
            password = "hardp123",
            foodbank_id = "1234",
            approved_for_admin_panel = True
            )

    def test_faq_page(self):
        """Navigate through admin panel to audit logs and verify all relevant information is displaying as intended"""
        page = self.browser.new_page()

        page.goto(f"{self.live_server_url}/login/")
        page.screenshot(path="screenshots/login_empty.png")
        page.fill('input[name="username"]', 'evanscott')
        page.fill('input[name="password"]', 'hardp123')
        page.screenshot(path="screenshots/login_filled.png")
        page.click('button[type="submit"]')

        page.wait_for_url(f"{self.live_server_url}/faqs/")
        page.screenshot(path="screenshots/faq.png")

        content = page.content()
        assert "No matching entries found" in content

        page.click('a.create-btn')
        page.wait_for_url(f"{self.live_server_url}/create_faq/")

        page.fill('textarea[name="question"]', "What are your working hours?")
        page.fill('textarea[name="answer"]', "8AM to 5PM")
        page.screenshot(path="screenshots/create_faq.png")
        page.click('button[type="submit"]')
        page.wait_for_url(f"{self.live_server_url}/faqs/")

        content = page.content()
        assert "What are your working hours?" in content
        assert "8AM to 5PM" in content
        page.screenshot(path="screenshots/added_faq.png")

        faq_row = page.locator("tr", has_text="What are your working hours?")
        edit_link = faq_row.locator("a.edit-btn").get_attribute("href")
        page.goto(f"{self.live_server_url}{edit_link}")
        page.fill('textarea[name="answer"]', "We open at 8AM and close at 5PM")
        page.screenshot(path="screenshots/edited_faq.png")
        page.click('button[type="submit"]')
        page.wait_for_url(f"{self.live_server_url}/faqs/")
        page.screenshot(path="screenshots/faq_edit.png")

        content = page.content()
        assert "We open at 8AM and close at 5PM" in content

        page.fill('input[name="q"]', "What are your working hours?")
        page.click('button.search-button')
        page.wait_for_url(f"{self.live_server_url}/faqs/?q=What+are+your+working+hours%3F&tag=")
        page_content = page.content()
        assert "We open at 8AM and close at 5PM" in page_content
        page.screenshot(path="screenshots/valid_search.png")

        page.goto(f"{self.live_server_url}/faqs/")
        page.fill('input[name="q"]', "Nonexistent")
        page.click('button.search-button')
        page.wait_for_url(f"{self.live_server_url}/faqs/?q=Nonexistent&tag=")
        page_content = page.content()
        assert "No matching entries found" in page_content
        page.screenshot(path="screenshots/invalid_search.png")

        page.goto(f"{self.live_server_url}/faqs/")
        faq_row = page.locator("tr", has_text="What are your working hours?")
        faq_row.locator("form button.delete-btn").click()
        page.wait_for_url(f"{self.live_server_url}/faqs/")
        page.screenshot(path="screenshots/delete_faq.png")

        content = page.content()
        assert "What are your working hours?" not in content
        assert "No matching entries found" in content

        page.close()
