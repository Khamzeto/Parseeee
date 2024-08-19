from flask import Flask, jsonify, request, render_template_string, send_from_directory
from pymongo import MongoClient
import os

app = Flask(__name__)

# Подключение к MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['parfumo']
collection = db['perfumes']

# Указываем путь к папке с изображениями
app.config['IMAGE_FOLDER'] = os.path.join(os.getcwd(), 'images')

# Маршрут для отображения страницы с парфюмами
@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Коллекция Парфюмов</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 20px;
            color: #333;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
        }

        h1 {
            text-align: center;
            color: #333;
        }

        #perfume-list {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 20px;
        }

        .perfume-item {
            background-color: #fff;
            border: 1px solid #ddd;
            padding: 10px;
            cursor: pointer;
            flex: 1 1 calc(33.333% - 10px);
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            text-align: center;
        }

        .perfume-item:hover {
            background-color: #f0f0f0;
        }

        #perfume-details {
            padding: 15px;
            background-color: #fff;
            border: 1px solid #ddd;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }

        .perfume-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .perfume-header img {
            max-width: 200px;
            height: auto;
        }

        .perfume-main {
            padding-left: 20px;
            flex-grow: 1;
        }

        .perfume-rating {
            color: #3a9d23;
            font-weight: bold;
        }

        .perfume-accords {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }

        .perfume-accord {
            padding: 5px 10px;
            border-radius: 20px;
            background-color: #eee;
        }

        .perfume-notes {
            margin-top: 20px;
        }

        .perfume-images {
            text-align: center;
            margin-top: 20px;
        }

        .perfume-images img {
            max-width: 100%;
            height: auto;
            margin-bottom: 10px;
            display: block;
            margin-left: auto;
            margin-right: auto;
        }

        .additional-images {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-top: 10px;
        }

        .additional-images img {
            max-width: 50px;
            height: auto;
            cursor: pointer;
        }

        .tags {
            margin-top: 15px;
        }

        .tag {
            display: inline-block;
            background-color: #eee;
            padding: 5px 10px;
            margin-right: 5px;
            border-radius: 20px;
            font-size: 14px;
        }

        .reviews {
            margin-top: 30px;
        }

        .review {
            border-top: 1px solid #ddd;
            padding: 10px 0;
        }

        .review-title {
            font-weight: bold;
            margin-bottom: 5px;
        }

        .review-body {
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Коллекция Парфюмов</h1>
        <div id="perfume-list">
            <!-- Список парфюмов будет загружен сюда -->
        </div>
        <div id="perfume-details">
            <!-- Детали парфюма будут отображаться здесь -->
        </div>
    </div>
    <script>
        document.addEventListener("DOMContentLoaded", () => {
            const perfumeListElement = document.getElementById('perfume-list');
            const perfumeDetailsElement = document.getElementById('perfume-details');

            // Функция для получения списка парфюмов
            function fetchPerfumes() {
                fetch('/perfumes')
                    .then(response => response.json())
                    .then(data => {
                        perfumeListElement.innerHTML = '';
                        data.forEach(perfume => {
                            const item = document.createElement('div');
                            item.className = 'perfume-item';
                            item.textContent = perfume.name;
                            item.addEventListener('click', () => fetchPerfumeDetails(perfume.perfume_id));
                            perfumeListElement.appendChild(item);
                        });
                    })
                    .catch(error => {
                        console.error('Ошибка при получении списка парфюмов:', error);
                    });
            }

            // Функция для получения деталей парфюма
            function fetchPerfumeDetails(perfumeId) {
                fetch(`/perfume/${encodeURIComponent(perfumeId)}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            perfumeDetailsElement.innerHTML = `<p>${data.error}</p>`;
                        } else {
                            const accordsHTML = data.accords.map(accord => `<div class="perfume-accord">${accord}</div>`).join('');
                            const reviewsHTML = data.reviews.map(review => `
                                <div class="review">
                                    <div class="review-title">${review.title}</div>
                                    <div class="review-body">${review.body}</div>
                                </div>
                            `).join('');
                            const tagsHTML = data.tags.map(tag => `<div class="tag">${tag}</div>`).join('');

                            // Формируем описание с ссылками
                            const descriptionHTML = data.description_links.reduce((desc, link) => {
                                return desc.replace(link.text, `<a href="${link.href}" target="_blank">${link.text}</a>`);
                            }, data.description);

                            perfumeDetailsElement.innerHTML = `
                                <div class="perfume-header">
                                    <img src="/images/${data.main_image}" alt="${data.name} основное изображение">
                                    <div class="perfume-main">
                                        <h2>${data.name}</h2>
                                        <p><strong>Бренд:</strong> ${data.brand}</p>
                                        <p><strong>Тип:</strong> ${data.type}</p>
                                        <p><strong>Рейтинг:</strong> <span class="perfume-rating">${data.rating}</span></p>
                                        <p><strong>Пол:</strong> ${data.gender}</p>
                                        <p><strong>Год выпуска:</strong> ${data.release_year}</p>
                                        <div class="perfume-accords">${accordsHTML}</div>
                                        <div class="additional-images">
                                            ${data.additional_images.map(img => `<img src="/images/${img}" alt="Дополнительное изображение">`).join('')}
                                        </div>
                                    </div>
                                </div>
                                <div class="perfume-description">
                                    <p>${descriptionHTML}</p>
                                </div>
                                <div class="perfume-notes">
                                    <p><strong>Ноты:</strong></p>
                                    <p><strong>Верхние ноты:</strong> ${data.notes.top_notes.join(', ')}</p>
                                    <p><strong>Средние ноты:</strong> ${data.notes.heart_notes.join(', ')}</p>
                                    <p><strong>Базовые ноты:</strong> ${data.notes.base_notes.join(', ')}</p>
                                </div>
                                <div class="tags">
                                    <h3>Теги</h3>
                                    ${tagsHTML}
                                </div>
                                <div class="reviews">
                                    <h3>Отзывы</h3>
                                    ${reviewsHTML}
                                </div>
                            `;
                        }
                    })
                    .catch(error => {
                        console.error('Ошибка при получении деталей парфюма:', error);
                    });
            }

            // Загружаем список парфюмов при загрузке страницы
            fetchPerfumes();
        });
    </script>
</body>
</html>
''')


# Маршрут для получения списка парфюмов
@app.route('/perfumes', methods=['GET'])
def get_perfumes():
    perfumes = collection.find({}, {"_id": 0, "name": 1, "perfume_id": 1})
    perfume_list = [{"name": perfume['name'], "perfume_id": perfume['perfume_id']} for perfume in perfumes]
    return jsonify(perfume_list)

# Маршрут для получения детальной информации о парфюме по perfume_id
# Маршрут для получения детальной информации о парфюме по perfume_id
@app.route('/perfume/<perfume_id>', methods=['GET'])
def get_perfume_details(perfume_id):
    perfume = collection.find_one({"perfume_id": perfume_id}, {"_id": 0})
    if perfume:
        # Преобразуем пути к изображениям, чтобы они работали с Flask
        perfume['main_image'] = os.path.basename(perfume['main_image'])
        perfume['additional_images'] = [os.path.basename(img) for img in perfume['additional_images']]
        return jsonify(perfume)
    else:
        return jsonify({"error": "Perfume not found"}), 404


# Маршрут для статических изображений
@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['IMAGE_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
