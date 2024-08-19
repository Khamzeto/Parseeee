import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from pymongo import MongoClient
from urllib.parse import urljoin
import requests
import os
import re
from concurrent.futures import ThreadPoolExecutor
import json

# Настройка Selenium
chrome_options = Options()
chrome_options.headless = True  # Включаем headless режим
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-popup-blocking")
chrome_options.add_argument("--disable-infobars")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

prefs = {"profile.managed_default_content_settings.images": 2}  # Отключаем загрузку изображений
chrome_options.add_experimental_option("prefs", prefs)

# Путь к драйверу ChromeDriver
service = Service('C:/Users/Khamzat/Desktop/chromedriver-win64/chromedriver-win64/chromedriver.exe')

# Создание экземпляра драйвера
driver = webdriver.Chrome(service=service, options=chrome_options)

# Устанавливаем тайм-аут на загрузку страницы
driver.set_page_load_timeout(300)

# Подключение к MongoDB
try:
    client = MongoClient('mongodb://localhost:27017/')
    db = client['parfumo']
    collection = db['perfumes']
    print("Connected to MongoDB successfully.")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    exit()

# Базовый URL
base_url = "https://www.parfumo.com"

# Функция перевода через неофициальный API Google Translate
def translate_text(text, target_lang='ru', src_lang='auto'):
    try:
        # URL для неофициального API Google Translate
        url = "https://translate.google.com/translate_a/single"

        # Параметры запроса
        params = {
            "client": "gtx",  # Используем "gtx", чтобы указать Google Translate API
            "sl": src_lang,  # Исходный язык (автоматическое определение)
            "tl": target_lang,  # Целевой язык
            "dt": "t",  # Тип перевода
            "q": text,  # Текст для перевода
        }

        # Заголовки для запроса
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # Выполнение запроса
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()

        # Парсинг результата
        translated_text = json.loads(response.text)[0][0][0]
        return translated_text

    except Exception as e:
        print(f"Translation failed: {e}")
        return text


def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def download_image(image_url, save_directory, perfume_name, image_type, image_index=None):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(image_url, headers=headers, stream=True)
        if response.status_code == 200:
            image_extension = image_url.split('.')[-1]
            sanitized_perfume_name = sanitize_filename(perfume_name)
            if image_type == 'main':
                image_path = os.path.join(save_directory, f"{sanitized_perfume_name}_main.{image_extension}")
            else:
                image_path = os.path.join(save_directory, f"{sanitized_perfume_name}_additional_{image_index}.{image_extension}")

            with open(image_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)

            print(f"Image saved at {image_path}")
            return image_path
        else:
            print(f"Failed to download image: {image_url}. Status code: {response.status_code}")
            return None

    except Exception as e:
        print(f"Error downloading image {image_url}: {e}")
        return None

def parse_notes(soup):
    notes = {'top_notes': [], 'heart_notes': [], 'base_notes': [], 'additional_notes': []}

    # Парсинг пирамиды нот, если она есть
    top_notes_elements = soup.select('div.pyramid_block.nb_t .clickable_note_img')
    for note in top_notes_elements:
        notes['top_notes'].append(translate_text(note.text.strip()))

    heart_notes_elements = soup.select('div.pyramid_block.nb_m .clickable_note_img')
    for note in heart_notes_elements:
        notes['heart_notes'].append(translate_text(note.text.strip()))

    base_notes_elements = soup.select('div.pyramid_block.nb_b .clickable_note_img')
    for note in base_notes_elements:
        notes['base_notes'].append(translate_text(note.text.strip()))

    # Парсинг нот в другом формате (как в вашем примере)
    additional_notes_elements = soup.select('div.notes_list div.nb_n span.clickable_note_img')
    for note in additional_notes_elements:
        note_text = note.text.strip()
        if note_text:
            notes['additional_notes'].append(translate_text(note_text))

    return notes
def parse_reviews(soup):
    reviews_data = []
    review_elements = soup.select('article.review')

    for review in review_elements:
        title_element = review.select_one('div.text-lg.bold span[itemprop="name"]')
        body_element = review.select_one('div[itemprop="reviewBody"] div.leading-7')

        if title_element and body_element:
            review_data = {
                "title": translate_text(title_element.text.strip()),
                "body": translate_text(body_element.text.strip())
            }
            reviews_data.append(review_data)

    return reviews_data

def parse_perfumers(soup):
    perfumers = []
    perfumers_element = soup.select('h2.text-lg.bold:-soup-contains("Perfumer") + div.w-100 a, h2.text-lg.bold:-soup-contains("Perfumers") + div.w-100 a')

    for perfumer in perfumers_element:
        perfumers.append(translate_text(perfumer.text.strip()))

    return perfumers

def parse_tags(soup):
    tags = []
    tag_elements = soup.select('div#tags_holder a.inline-block.text-lg.grey')

    for tag in tag_elements:
        tags.append(translate_text(tag.text.strip()))

    return tags

def parse_similar_perfumes(soup):
    similar_perfumes = []

    try:
        similar_button = WebDriverWait(driver, 4).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.action_similar[data-type="all"]'))
        )
        driver.execute_script("arguments[0].scrollIntoView();", similar_button)
        similar_button.click()

        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.sim_item'))
        )

        soup = BeautifulSoup(driver.page_source, 'html.parser')

    except Exception:
        print("Button to show all similar perfumes not found or not needed.")

    # Независимо от того, была ли найдена и нажата кнопка, парсим имеющиеся данные
    similar_items = soup.select('div.sim_item')
    for item in similar_items:
        s_id = item.get('data-s_id')
        if s_id:
            similar_perfumes.append(s_id)

    return similar_perfumes


def parse_og_image_id(soup):
    og_image_tag = soup.select_one('meta[property="og:image"]')
    if og_image_tag:
        og_image_url = og_image_tag.get('content')
        og_image_id = og_image_url.split('/')[-1].split('_')[0]
        return og_image_id
    return None

def parse_perfume_type(soup):
    perfume_type_element = soup.select_one('span.p_con.label_a.pointer.upper')
    if perfume_type_element:
        perfume_type = perfume_type_element.text.strip()

        # Переводим с французского на русский, используя корректные параметры
        return translate_text(perfume_type, target_lang='ru', src_lang='fr')

    return None

def parse_perfume_page(perfume_url):
    try:
        driver.get(perfume_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.p_name_h1[itemprop="name"]'))
        )
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        name_element = soup.select_one('h1.p_name_h1[itemprop="name"]')
        if name_element:
            brand_element = name_element.select_one('span[itemprop="brand"] span[itemprop="name"]')

            perfume_data = {
                "name": name_element.contents[0].strip(),
                "brand": brand_element.text.strip() if brand_element else "Unknown"
            }

            perfume_id = parse_og_image_id(soup)
            if perfume_id:
                perfume_data['perfume_id'] = perfume_id
            else:
                print(f"Perfume ID not found for {perfume_url}")
                return  # Выход из функции, если perfume_id не найден

            existing_perfume = collection.find_one({"perfume_id": perfume_id})
            if existing_perfume:
                print(f"Perfume with ID {perfume_id} already exists, skipping.")
                return  # Выход из функции, если запись уже существует

            description_element = soup.select_one('span[itemprop="description"]')
            if description_element:
                links = description_element.find_all('a')
                links_info = []
                for link in links:
                    href = link['href'].replace(base_url, '')
                    text = link.text.strip()
                    links_info.append({'text': text, 'href': href})
                    link.replace_with(text)

                translated_description = translate_text(description_element.text.strip())
                perfume_data['description'] = translated_description
                perfume_data['description_links'] = links_info

            perfume_data['notes'] = parse_notes(soup)

            ratings = soup.select_one('div.barfiller_element[data-type="bottle"] .bold.green')
            perfume_data['rating'] = ratings.text.strip() if ratings else "No rating"

            gender_icon = soup.select_one('div.p_gender_big i')
            if gender_icon:
                gender_class = gender_icon['class'][1]
                perfume_data['gender'] = gender_class

            accords = soup.select('div.s-circle-container div.text-xs.grey')
            perfume_data['accords'] = [translate_text(accord.text.strip()) for accord in accords]

            release_year_element = soup.select_one('span.label_a')
            if release_year_element:
                release_year = re.search(r'\b\d{4}\b', release_year_element.text)
                if release_year:
                    perfume_data['release_year'] = release_year.group(0)
                else:
                    perfume_data['release_year'] = translate_text(release_year_element.text.strip())

            perfume_type = parse_perfume_type(soup)
            if perfume_type:
                perfume_data['type'] = perfume_type

            main_image_element = soup.select_one('img.p-main-img[itemprop="image"]')
            if main_image_element:
                main_image_url = main_image_element['src']
                save_directory = 'images'
                os.makedirs(save_directory, exist_ok=True)
                main_image_path = download_image(main_image_url, save_directory, perfume_data['name'], image_type='main')
                if main_image_path:
                    perfume_data['main_image'] = main_image_path

            additional_image_elements = soup.select('div#p_imagery_holder a.imagery_item')
            additional_image_paths = []
            for index, image_element in enumerate(additional_image_elements):
                image_url = image_element['href']
                image_path = download_image(image_url, save_directory, perfume_data['name'], image_type='additional',
                                            image_index=index)
                if image_path:
                    additional_image_paths.append(image_path)
            perfume_data['additional_images'] = additional_image_paths

            perfume_data['reviews'] = parse_reviews(soup)
            perfume_data['perfumers'] = parse_perfumers(soup)

            similar_perfumes = parse_similar_perfumes(soup)
            perfume_data['similar_perfumes'] = similar_perfumes

            try:
                tags_button = WebDriverWait(driver, 4).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.action_inspiration[data-type="tags"]'))
                )
                tags_button.click()

                WebDriverWait(driver, 4).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div#tags_holder a.inline-block.text-lg.grey'))
                )

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                tags = parse_tags(soup)

            except Exception as e:
                print("Tags section not found or not needed.")
                tags = []

            perfume_data['tags'] = tags

            result = collection.replace_one({"perfume_id": perfume_id}, perfume_data, upsert=True)
            if result.upserted_id:
                print(f"Inserted perfume with ID: {result.upserted_id}")
            else:
                print(f"Updated perfume with ID: {perfume_id}")

        else:
            print(f"Name element not found for {perfume_url}")

    except Exception as e:
        print(f"Error parsing perfume page {perfume_url}: {e}")


def parse_brand_perfumes(brand_url):
    time.sleep(5)
    try:
        page_number = 1
        while True:
            current_url = f"{brand_url}?current_page={page_number}&v=grid&o=n_asc&g_f=1&g_m=1&g_u=1"
            driver.get(current_url)
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            perfume_links = soup.select('div.col-normal div.name a[href]')
            if not perfume_links:
                break

            # Открываем несколько вкладок для парфюмов
            for link in perfume_links:
                perfume_url = urljoin(base_url, link['href'])
                driver.execute_script("window.open(arguments[0]);", perfume_url)

            # Обрабатываем каждую вкладку
            for handle in driver.window_handles[1:]:
                driver.switch_to.window(handle)
                parse_perfume_page(driver.current_url)
                driver.close()  # Закрываем вкладку после завершения обработки

            # Возвращаемся на основную вкладку
            driver.switch_to.window(driver.window_handles[0])

            next_page = soup.select_one(f'div.numbers div a[href*="current_page={page_number+1}"]')
            if next_page:
                page_number += 1
            else:
                break

    except Exception as e:
        print(f"Error parsing brand page {brand_url}: {e}")


def parse_all_brands():

    try:
        driver.get(base_url + "/Brands/c")
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        brand_links = soup.select('div.brands_list a[href]')
        for link in brand_links:
            brand_url = urljoin(base_url, link['href'])
            print(f"Parsing brand: {brand_url}")
            parse_brand_perfumes(brand_url)

    except Exception as e:
        print(f"Error parsing brands list: {e}")

if __name__ == "__main__":
    parse_all_brands()
    driver.quit()

