from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.staticfiles import StaticFiles
import os
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
import requests
from lxml import html
import threading
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from typing import Optional
import uuid
from datetime import datetime

# Create FastAPI app instance
app = FastAPI()

# Set up CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Firebase Admin SDK
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Function to fetch Flipkart product details using Selenium
def get_flipkart_details(url):
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        try:
            price_element = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div._30jeq3._16Jk6d, div.Nx9bqj.CxhGGd"))
            )
            price = price_element.text.strip()
        except Exception as e:
            price = f"Failed to extract price: {str(e)}"
        try:
            stock = None
            for selector in [
                "div._16FRp0", "div._2JC05C", "div._22vQVX", "div._1TPvTK", "div._2Xfa2_",
                "span._2JC05C", "span._16FRp0", "div._3xFhiH", "div._2Tpdn3", "div._2d5JIQ", "div.R4PyiO"
            ]:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    text = el.text.strip()
                    if any(x in text.lower() for x in ["in stock", "out of stock", "sold out", "only", "left", "available", "hurry"]):
                        stock = text
                        break
                if stock:
                    break
            if not stock:
                page_text = driver.page_source.lower()
                if "currently unavailable" in page_text:
                    stock = "Currently unavailable"
                else:
                    stock = "Stock info not available"
        except Exception:
            stock = "Stock info not available"
        try:
            image_url = None
            for selector in [
                "img._396cs4", "img._2r_T1I", "img._1Nyybr", "img._1A6k1S", "img._3togXc", "img._2amPTt", "img.DByuf4.IZexXJ.jLEJ7H"
            ]:
                images = driver.find_elements(By.CSS_SELECTOR, selector)
                for img in images:
                    src = img.get_attribute("src")
                    if src and src.startswith("http"):
                        image_url = src
                        break
                if image_url:
                    break
        except Exception:
            image_url = None
        if not stock and price and not ("failed" in price.lower()):
            stock = "In stock"
        driver.quit()
        return price, stock, image_url
    except Exception as e:
        print(f"Flipkart Error: {e}")
        return None, "Error fetching details", None

def get_amazon_details(url):
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        try:
            price_whole = driver.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.strip()
            price_fraction = driver.find_element(By.CSS_SELECTOR, "span.a-price-fraction").text.strip()
            price = f"{price_whole}.{price_fraction}"
        except Exception:
            try:
                price = driver.find_element(By.CSS_SELECTOR, "span.a-offscreen").text.strip()
            except Exception:
                price = ""
        try:
            stock_element = driver.find_element(By.CSS_SELECTOR, "#availability span")
            stock = stock_element.text.strip()
        except Exception:
            stock = "Stock info not available"
        try:
            image_element = driver.find_element(By.CSS_SELECTOR, "img#landingImage")
            image_url = image_element.get_attribute("src")
        except Exception:
            image_url = None
        driver.quit()
        return price, stock, image_url
    except Exception as e:
        print(f"Amazon Error: {e}")
        return None, "Error fetching details", None

def get_product_details(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        time.sleep(random.uniform(5, 15))
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        price, stock = None, "Stock info not available"
        if "amazon" in url:
            price_element = soup.select_one("span.a-price-whole")
            price_fraction = soup.select_one("span.a-price-fraction")
            stock_element = soup.select_one("#availability span")
            price = f"{price_element.text.strip()}{price_fraction.text.strip()}" if price_element and price_fraction else None
            stock = stock_element.text.strip() if stock_element else stock
        elif "flipkart" in url:
            price, stock = get_flipkart_details(url)
        return price, stock
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None, "Error fetching details"

def get_product_details_with_image(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        time.sleep(random.uniform(5, 15))
        if "amazon" in url:
            return get_amazon_details(url)
        elif "flipkart" in url:
            return get_flipkart_details(url)
        else:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            return None, "Stock info not available", None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None, "Error fetching details", None

def send_fcm_notification(user_id, title, body, url=None):
    user_doc = db.collection("users").document(user_id).get()
    if user_doc.exists:
        fcm_token = user_doc.to_dict().get("fcm_token")
        if fcm_token:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                token=fcm_token,
                data={"url": url or ""},
            )
            try:
                messaging.send(message)
            except Exception as e:
                print(f"FCM send error: {e}")

def add_notification(user_id, message, url=None, type_="info"):
    notif_id = str(uuid.uuid4())
    notif_data = {
        "message": message,
        "url": url,
        "type": type_,
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    db.collection("users").document(user_id).collection("notifications").document(notif_id).set(notif_data)
    send_fcm_notification(user_id, "PricePing Alert", message, url)

# Background function to check stock daily
def track_stock_daily(url, phone):
    while True:
        _, stock = get_product_details(url)
        if stock:
            add_notification(phone, f"Daily stock update: {stock}\n{url}")
        time.sleep(86400)

# Background function to check stock every 30 min if low
def track_low_stock(url, phone):
    while True:
        _, stock = get_product_details(url)
        if stock and any(x in stock.lower() for x in ["only", "left", "low stock", "out of stock"]):
            add_notification(phone, f"Stock running low! Current status: {stock}\n{url}")
        time.sleep(1800)

@app.post("/toggle_product/")
async def toggle_product(user_id: str = Form(...), product_id: str = Form(...), active: bool = Form(...)):
    try:
        now = datetime.utcnow().isoformat() + 'Z'
        db.collection("users").document(user_id).collection("products").document(product_id).update({
            "active": active,
            "last_checked": now
        })
        return {"message": f"Tracking {'resumed' if active else 'paused'} for product.", "last_checked": now}
    except Exception as e:
        return {"error": str(e)}

@app.post("/track/")
async def track_price(url: str = Form(...), threshold_price: str = Form(...), phone: str = Form(...), user_id: Optional[str] = Form(None)):
    try:
        current_price, stock = get_product_details(url)
        if current_price is None:
            if user_id:
                add_notification(user_id, "Error: Could not fetch product details.", url, "error")
            return {"error": "Could not fetch product details"}
        if user_id:
            add_notification(user_id, f"📌 Tracking started!\n💰 Current price: ₹{current_price}\n📦 Stock: {stock}", url, "info")
        try:
            current_price_numeric = float(current_price.replace(',', '').strip().replace('₹', ''))
            threshold_price_numeric = float(threshold_price.replace(',', '').strip())
            if current_price_numeric <= threshold_price_numeric:
                if user_id:
                    add_notification(user_id, f"🎉 Price drop alert!\n💰 Now ₹{current_price}!", url, "price_drop")
                return {"message": "Price dropped! Notification sent."}
            else:
                return {"message": f"Tracking started. Current price: ₹{current_price}. Stock: {stock}"}
        except ValueError:
            return {"message": f"Tracking started. Current price: ₹{current_price}. Stock: {stock}. Could not compare price."}
    except Exception as e:
        if user_id:
            add_notification(user_id, f"Error: {str(e)}", url, "error")
        return {"error": str(e)}

@app.post("/register_product/")
async def register_product(request: Request, url: str = Form(...), threshold_price: str = Form(...), phone: str = Form(...), user_id: Optional[str] = Form(None)):
    try:
        current_price, stock, image_url = get_product_details_with_image(url)
        product_id = str(uuid.uuid4())
        now = datetime.utcnow()
        product_data = {
            "url": url,
            "threshold_price": threshold_price,
            "phone": phone,
            "current_price": current_price,
            "stock": stock,
            "image_url": image_url,
            "created_at": firestore.SERVER_TIMESTAMP,
            "last_checked": now.isoformat() + 'Z',
            "active": True
        }
        if user_id:
            db.collection("users").document(user_id).collection("products").document(product_id).set(product_data)
            user_doc_ref = db.collection("users").document(user_id)
            user_doc = user_doc_ref.get()
            if not user_doc.exists or user_doc.to_dict().get("phone") != phone:
                user_doc_ref.set({"phone": phone}, merge=True)
        else:
            db.collection("products").document(product_id).set(product_data)
        return {"message": "Product registered and tracking started.", "product_id": product_id}
    except Exception as e:
        return {"error": str(e)}

@app.get("/user_products/")
async def get_user_products(user_id: str):
    try:
        products_ref = db.collection("users").document(user_id).collection("products")
        products = [doc.to_dict() | {"id": doc.id} for doc in products_ref.stream()]
        for p in products:
            if "last_checked" not in p:
                p["last_checked"] = None
            if "active" not in p:
                p["active"] = True
        return {"products": products}
    except Exception as e:
        return {"error": str(e)}

@app.post("/save_tracking_report/")
async def save_tracking_report(user_id: str = Form(...), product_id: str = Form(...), report: str = Form(...)):
    try:
        report_id = str(uuid.uuid4())
        report_data = {
            "product_id": product_id,
            "report": report,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        db.collection("users").document(user_id).collection("reports").document(report_id).set(report_data)
        return {"message": "Tracking report saved.", "report_id": report_id}
    except Exception as e:
        return {"error": str(e)}

def check_all_users_products_and_send_notifications():
    try:
        print("[DEBUG] Running product check at", datetime.utcnow().isoformat())
        users_ref = db.collection("users").stream()
        for user_doc in users_ref:
            user_id = user_doc.id
            products_ref = db.collection("users").document(user_id).collection("products").stream()
            for product_doc in products_ref:
                product = product_doc.to_dict()
                url = product.get("url")
                threshold_price = product.get("threshold_price")
                last_price = product.get("current_price")
                active = product.get("active", True)
                if not (url and threshold_price) or not active:
                    continue
                print(f"[DEBUG] Checking product {product_doc.id} for user {user_id}")
                current_price, stock, _ = get_product_details_with_image(url)
                now = datetime.utcnow().isoformat() + 'Z'
                try:
                    db.collection("users").document(user_id).collection("products").document(product_doc.id).update({
                        "current_price": current_price,
                        "stock": stock,
                        "last_checked": now
                    })
                    print(f"[DEBUG] Updated last_checked for product {product_doc.id} to {now}")
                except Exception as update_e:
                    print(f"[ERROR] Firestore update failed for product {product_doc.id}: {update_e}")
                try:
                    current_price_numeric = float(str(current_price).replace(',', '').replace('₹', '').strip())
                    threshold_price_numeric = float(str(threshold_price).replace(',', '').strip())
                    if current_price_numeric <= threshold_price_numeric:
                        add_notification(user_id, f"🎉 Price drop alert! Now ₹{current_price}!", url, "price_drop")
                except Exception:
                    pass
                if stock and any(x in stock.lower() for x in ["only", "left", "low stock", "out of stock"]):
                    add_notification(user_id, f"⚠ Stock update: {stock}", url, "stock")
    except Exception as e:
        print(f"[ERROR] Error in background notification job: {e}")

def background_price_check_loop():
    print("[DEBUG] Background price check thread started.")
    while True:
        check_all_users_products_and_send_notifications()
        time.sleep(10)

threading.Thread(target=background_price_check_loop, daemon=True).start()
# Start background thread to check all users' products every 10 seconds

def background_price_check_loop():
    while True:
        check_all_users_products_and_send_notifications()
        time.sleep(10)

threading.Thread(target=background_price_check_loop, daemon=True).start()

@app.post("/test_push/")
async def test_push(user_id: str):
    send_fcm_notification(user_id, "Test Notification", "This is a test push notification from backend.")
    return {"status": "sent"}

@app.get("/admin/users")
async def admin_get_all_users():
    try:
        users_ref = db.collection("users").stream()
        users = []
        for user_doc in users_ref:
            user_data = user_doc.to_dict() or {}
            user_id = user_doc.id
            email = user_data.get("email", "")
            products_ref = db.collection("users").document(user_id).collection("products").stream()
            products = [p.to_dict() | {"id": p.id} for p in products_ref]
            users.append({"uid": user_id, "email": email, "products": products})
        return {"users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.mount(
    "/",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "frontend", "build"), html=True),
    name="static",
)