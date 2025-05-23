from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from datetime import datetime
import time
import pandas as pd
import os
import json
import random

def setup_driver():
    options = Options()
    # Uncomment for headless mode (useful for automated servers)
    # options.add_argument('--headless')  
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # Ignore SSL errors (more comprehensive)
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--incognito')

    # Set realistic user agent
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    options.add_argument(f'user-agent={user_agent}')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def scrape_flipkart_mobiles(driver, pages=40):
    all_products = []
    
    for page in range(1, pages + 1):
        url = f"https://www.flipkart.com/search?q=mobiles&page={page}"
        print(f"\nScraping page {page}: {url}")
        
        try:
            driver.get(url)
            print("Page title:", driver.title)
            time.sleep(3 + random.uniform(1, 2))  # 3 to 5 seconds delay to mimic human browsing
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            # Wait for product containers to load, improved selector
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-id], div._1AtVbE, div._2kHMtA"))
            )
            time.sleep(2)  # Additional delay for stability
            
            # Save page source for debugging
            if not os.path.exists('debug'):
                os.makedirs('debug')
            with open(f'debug/page_{page}.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Find all potential product containers
            listings = soup.select("div[data-id], div._1AtVbE, div._2kHMtA, div._1xHGtK")
            print(f"Found {len(listings)} product containers")
            
            # Debug: Save first product container HTML
            if listings:
                with open(f'debug/product_sample_{page}.html', 'w', encoding='utf-8') as f:
                    f.write(str(listings[0]))
            
            # Extract data from each product
            page_products = []
            for idx, item in enumerate(listings, 1):
                product = scrape_product(item)
                if product:
                    page_products.append(product)
                    print(f"[Page {page}] Product {idx}: {product['title'][:30]}... (₹{product['price']})")
            
            all_products.extend(page_products)
            print(f"Page {page} complete - Valid products: {len(page_products)}")
            if not page_products:
                print(f"No valid products found on page {page}. Stopping early.")
                break
            
        except Exception as e:
            print(f"Error scraping page {page}: {str(e)[:100]}")
            continue
    
    return all_products
def scrape_product(item):
    """Extract data from a single product item, including image and link"""
    try:
        title = (item.select_one("div.KzDlHZ") or 
                 item.select_one("div._4rR01T") or
                 item.select_one("a.s1Q9rs") or
                 item.select_one("a.IRpwTa"))
        
        price = (item.select_one("div._30jeq3") or
                 item.select_one("div._30jeq3._1_WHN1") or
                 item.select_one("div.Nx9bqj"))
        
        rating = (item.select_one("div.XQDdHH") or
                  item.select_one("div._3LWZlK") or
                  item.find('div', {'class': lambda x: x and 'rating' in x.lower()}))
        
        reviews = (item.select_one("span.Wphh3N") or
                   item.select_one("span._2_R_DZ") or
                   item.find('span', text=lambda x: x and ('ratings' in x.lower() or 'reviews' in x.lower())))
        
        specs = [li.text for li in item.select("li.J+igdf, li.rgWa7D, li._3YhLQA")]
        
        delivery = (item.select_one("div.yiggsN") or
                    item.select_one("div._3tcB5a") or
                    item.find('div', text=lambda x: x and 'delivery' in x.lower()))
        
        # Product link
        a_tag = item.select_one("a.CGtC98") or item.select_one("a._1fQZEK") or item.select_one("a.IRpwTa")
        product_url = "https://www.flipkart.com" + a_tag["href"] if a_tag and a_tag.has_attr("href") else None

        # Image URL (including support for lazy loading)
        img_tag = item.select_one("img.DByuf4") or item.select_one("img._396cs4") or item.find("img")
        image_url = None
        if img_tag:
            image_url = img_tag.get("src") or img_tag.get("data-src")

        if not title or not price:
            return None

        return {
            "timestamp": datetime.now().isoformat(),
            "title": title.text.strip(),
            "price": int(price.text.replace("₹", "").replace(",", "").strip()),
            "rating": float(rating.text.strip().split()[0]) if rating else None,
            "reviews": reviews.text.strip() if reviews else None,
            "specifications": " | ".join(specs) if specs else None,
            "delivery": delivery.text.strip() if delivery else None,
            "product_url": product_url,
            "image_url": image_url
        }
    except Exception as e:
        print(f"Error parsing product: {str(e)[:100]}")
        return None


def save_data(data, filename='flipkart_mobiles.csv'):
    try:
        df = pd.DataFrame(data)
        
        # Save to CSV
        df.to_csv(filename, index=False)
        print(f"\nSaved {len(data)} products to {filename}")
        
        # Also save as JSON for debugging
        json_file = filename.replace('.csv', '.json')
        df.to_json(json_file, orient='records', indent=2)
        print(f"Data also saved as {json_file} for inspection")
        
    except Exception as e:
        print(f"Failed to save data: {e}")

if __name__ == "__main__":
    print("Starting Flipkart Mobile Scraper...")
    
    driver = setup_driver()
    try:
        data = scrape_flipkart_mobiles(driver, pages=3)
        if data:
            save_data(data)
            print("\nScraping completed successfully!")
        else:
            print("\nScraping completed but no products were found.")
            print("Please check the debug HTML files in the 'debug' folder.")
    except Exception as e:
        print(f"\nScraping failed: {e}")
    finally:
        driver.quit()
        print("Driver closed.")
        print("Starting Flipkart Electronics Scraper...")





