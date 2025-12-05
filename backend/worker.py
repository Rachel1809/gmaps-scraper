import threading
import time
import random
import re
from typing import Optional, Set, Dict, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class ScraperWorker:
    def __init__(self, keyword: str, headless: bool, callback: callable, ignore_urls: list = None):
        self.keyword = keyword
        self.headless = headless
        self.callback = callback
        self.ignore_urls: Set[str] = set(ignore_urls) if ignore_urls else set()
        
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self.driver: Optional[webdriver.Chrome] = None
        self.processed_urls: Set[str] = self.ignore_urls.copy()

    def start(self):
        """Starts the scraping logic in a separate daemon thread."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_logic, daemon=True)
        self._thread.start()

    def stop(self):
        """Signals the thread to stop and cleans up the driver."""
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._cleanup_driver()

    def _cleanup_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def _setup_driver(self):
        """Initializes the Chrome WebDriver with robust options."""
        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        
        # Stability arguments for various environments (Docker, Linux, etc.)
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--window-size=1280,800")
        opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.callback("log", "> [System] Launching Chrome Driver...")
        try:
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=opts)
            self.callback("log", "✅ Driver initialized.")
        except Exception as e:
            self.callback("log", "❌ FATAL: Chrome Driver Failed.")
            raise e

    def _broadcast_view(self):
        """Captures and sends a screenshot to the UI."""
        if self.driver and self.is_running:
            try:
                b64_data = self.driver.get_screenshot_as_base64()
                self.callback("image", b64_data)
            except Exception:
                pass

    # =========================================================================
    # DOM CONTEXT & HEURISTICS
    # =========================================================================

    def _get_active_main_context(self) -> WebElement:
        """
        Identifies the currently active 'Details' pane in Google Maps.
        Maps often keeps the 'List View' in DOM; we need the one with the visible H1.
        """
        try:
            mains = self.driver.find_elements(By.CSS_SELECTOR, "div[role='main']")
            # Iterate backwards as the newest panel (Details) is usually appended last
            for m in reversed(mains):
                try:
                    h1 = m.find_element(By.TAG_NAME, "h1")
                    if h1.is_displayed():
                        return m
                except Exception:
                    continue
            if mains:
                return mains[-1]
        except Exception:
            pass
        
        # Fallbacks
        try:
            return self.driver.find_element(By.CSS_SELECTOR, "div[role='main']")
        except Exception:
            return self.driver.find_element(By.TAG_NAME, "body")

    def _extract_name(self) -> str:
        """Polls for the place name (H1) to ensure the detail panel is fully loaded."""
        end_time = time.time() + 3.0
        while time.time() < end_time:
            try:
                context = self._get_active_main_context()
                h1_list = context.find_elements(By.TAG_NAME, "h1")
                for h1 in h1_list:
                    text = h1.text.strip()
                    # Filter out navigation headers like "Results for..."
                    if text and "Result" not in text and "Showing" not in text:
                        return text
            except Exception:
                pass
            time.sleep(0.15)
        return "Unknown Name"

    def _extract_rating(self) -> str:
        """Extracts rating using visual text first, then accessibility labels."""
        try:
            context = self._get_active_main_context()
            
            # Strategy 1: Visual Text (e.g., "4.7")
            # Strict regex to avoid matching integers like "5" (from "5 stars" filter)
            try:
                elements = context.find_elements(By.XPATH, ".//div[string-length(text()) < 6] | .//span[string-length(text()) < 6]")
                for el in elements:
                    text = el.text.strip()
                    if re.match(r'^\d[\.,]\d$', text):
                        val = float(text.replace(',', '.'))
                        if 1.0 <= val <= 5.0:
                            return text.replace(',', '.')
            except Exception:
                pass

            # Strategy 2: Accessibility Labels
            xpath_attempts = [".//span[contains(@aria-label, 'stars')]", ".//span[@role='img']"]
            for xpath in xpath_attempts:
                try:
                    els = context.find_elements(By.XPATH, xpath)
                    for el in els:
                        aria = el.get_attribute("aria-label")
                        if not aria: continue
                        # Match "4.7 stars" or "Rated 4.7"
                        match = re.search(r'(\d[\.,]\d) stars', aria) or re.search(r'Rated (\d[\.,]\d)', aria)
                        if match:
                            return match.group(1).replace(',', '.')
                except Exception:
                    continue
        except Exception:
            pass
        return "N/A"

    def _extract_link(self, clicked_href: str) -> str:
        """Prioritizes the clicked href, falls back to current URL if it's a place link."""
        if clicked_href and "/maps/place/" in clicked_href:
            return clicked_href
        try:
            current = self.driver.current_url
            if "/maps/place/" in current:
                return current
        except Exception:
            pass
        return "N/A"

    def _extract_website(self) -> str:
        """Extracts website URL from authority buttons or links."""
        try:
            context = self._get_active_main_context()
            # Try specific authority ID
            try:
                el = context.find_element(By.CSS_SELECTOR, "[data-item-id='authority']")
                if el.tag_name == 'a':
                    return el.get_attribute('href') or "N/A"
                text = el.text.strip()
                if text: return text
                
                # Nested text fallback
                inner = el.find_element(By.CSS_SELECTOR, "div[class*='fontBodyMedium']")
                return inner.text.strip()
            except Exception:
                pass
            
            # Fallback: Globe Icon
            xpath = ".//button[descendant::img[contains(@src, 'public_gm')]]"
            btn = context.find_element(By.XPATH, xpath)
            return btn.text.strip()
        except Exception:
            pass
        return "N/A"

    def _extract_detail(self, icon_key: str, button_key: str = None) -> str:
        """Generic extractor for fields like Phone/Address based on Icons or Data IDs."""
        try:
            context = self._get_active_main_context()
            # Strategy 1: Icon
            try:
                xpath = f".//button[descendant::img[contains(@src, '{icon_key}')]]//div[contains(@class, 'fontBodyMedium')]"
                return context.find_element(By.XPATH, xpath).text.strip()
            except Exception:
                pass
            
            # Strategy 2: Data ID
            if button_key:
                try:
                    xpath = f".//button[contains(@data-item-id, '{button_key}')]"
                    return context.find_element(By.XPATH, xpath).text.strip()
                except Exception:
                    pass
        except Exception:
            pass
        return "N/A"

    # =========================================================================
    # CORE LOGIC
    # =========================================================================

    def _process_single_item(self, link_el: WebElement) -> None:
        """Click, wait, scrape, and report a single item."""
        try:
            # 1. Skip Ads/Sponsored
            try:
                text_content = link_el.text + link_el.find_element(By.XPATH, "./..").text
                if "Sponsored" in text_content:
                    self.callback("log", "⚠️ Skipping Sponsored result")
                    return
            except Exception:
                pass

            # 2. Click Item
            href = link_el.get_attribute("href")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", link_el)
            link_el.click()

            # 3. Wait for Detail Panel Load (H1)
            try:
                WebDriverWait(self.driver, 3).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            except Exception:
                pass # Proceed to extraction heuristics anyway

            self._broadcast_view()

            # 4. Extract Data
            data = {
                'name': self._extract_name(),
                'rating': self._extract_rating(),
                'link': self._extract_link(href),
                'website': self._extract_website(),
                'address': self._extract_detail("place_gm", "address"),
                'phone': self._extract_detail("phone_gm", "phone")
            }

            self.callback("row", data)
            self.callback("log", f"Extracted: {data['name']}")
            
            # Human-like delay
            time.sleep(random.uniform(0.5, 1.0))

        except Exception as e:
            self.callback("log", f"⚠️ Error processing item: {str(e)[:50]}")

    def _scroll_to_load(self, feed_element, current_count):
        """Scrolls the feed to load more items."""
        self.callback("log", "> Scrolling to find new items...")
        if feed_element:
            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", feed_element)
        else:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # Wait for items to increase
        try:
            WebDriverWait(self.driver, 3).until(
                lambda d: len(d.find_elements(By.XPATH, "//a[contains(@href, '/maps/place')]")) > current_count
            )
        except Exception:
            time.sleep(1.5) # Hard wait if condition times out
        
        self._broadcast_view()

    def _run_logic(self):
        try:
            self._setup_driver()
            
            url = f"https://www.google.com/maps/search/{self.keyword}"
            self.callback("log", f"> Navigating: {url}")
            self.driver.get(url)
            
            wait = WebDriverWait(self.driver, 15)
            
            # Attempt to locate the Feed container (Left Sidebar)
            try:
                feed = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@role, 'feed')]")))
                self.callback("log", "> Feed loaded.")
            except Exception:
                self.callback("log", "⚠️ Feed container not detected. Using fallback scroll.")
                feed = None
            
            if self.processed_urls:
                self.callback("log", f"> Resuming... Ignoring {len(self.processed_urls)} processed items.")

            scroll_fail_count = 0
            self._broadcast_view()

            while self.is_running:
                # 1. Collect Links
                all_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/maps/place')]")
                
                # 2. Filter New Links (Resume Logic)
                new_links = []
                for l in all_links:
                    href = l.get_attribute("href")
                    if href and href not in self.processed_urls:
                        new_links.append(l)

                # 3. Decision: Scroll or Scrape
                if not new_links:
                    self._scroll_to_load(feed, len(all_links))
                    scroll_fail_count += 1
                    if scroll_fail_count > 4:
                        self.callback("log", "> End of list reached or no new items found.")
                        break
                    continue
                
                # Reset scroll fail count if we found items
                scroll_fail_count = 0
                
                # 4. Process Batch
                for link_el in new_links:
                    if not self.is_running: break
                    
                    href = link_el.get_attribute("href")
                    # Double check in case of duplicates in current batch
                    if href in self.processed_urls: continue
                    
                    self.processed_urls.add(href)
                    self._process_single_item(link_el)

        except Exception as e:
            self.callback("log", f"❌ Worker Error: {str(e)}")
        finally:
            self.callback("status", "STOPPED")
            self.callback("log", "🛑 Scraper Stopped.")
            self._cleanup_driver()