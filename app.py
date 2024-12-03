from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Настройка строки подключения к базе данных PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://postgres:2006yura@localhost/swears'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация SQLAlchemy
db = SQLAlchemy(app)

class PowerfulHumiliation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(100), unique=True, nullable=False)

class WeakHumiliation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(100), unique=True, nullable=False)

with app.app_context():
    db.create_all()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/page/<int:page>', methods=['GET'])
def swears(page=1):
    per_page = 10  # Количество унижений на одной странице
    start = (page - 1) * per_page

    if page < 1:
        return jsonify({"error": "Page number must be 1 or higher"}), 400

    powerful_swears = PowerfulHumiliation.query.offset(start).limit(per_page).all()
    weak_swears = WeakHumiliation.query.offset(start).limit(per_page).all()

    if not powerful_swears and not weak_swears:
        return jsonify({"message": "No humiliations found on this page"}), 404

    total_pages_powerful = (PowerfulHumiliation.query.count() + per_page - 1) // per_page
    total_pages_weak = (WeakHumiliation.query.count() + per_page - 1) // per_page

    powerful = [{'text': swear.text} for swear in powerful_swears]
    weak = [{'text': swear.text} for swear in weak_swears]

    return render_template(
        'swears.html',
        powerful=powerful,
        weak=weak,
        page=page,
        total_pages_powerful=total_pages_powerful,
        total_pages_weak=total_pages_weak
    )


@app.route('/power', methods=['POST'])
def add_power():
    data = request.get_json()  # Чтение данных из JSON
    description = data.get('description')
    if not description or not description.strip():
        return jsonify({"error": "Description cannot be empty"}), 400

    humiliation = PowerfulHumiliation(text=description.strip())
    try:
        db.session.add(humiliation)
        db.session.commit()
        return jsonify({"message": "Powerful humiliation added successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Unable to add humiliation. It might already exist."}), 400


@app.route('/weakness', methods=['POST'])
def add_weakness():
    data = request.get_json()  # Чтение данных из JSON
    description = data.get('description')
    if not description or not description.strip():
        return jsonify({"error": "Description cannot be empty"}), 400

    humiliation = WeakHumiliation(text=description.strip())
    try:
        db.session.add(humiliation)
        db.session.commit()
        return jsonify({"message": "Weak humiliation added successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Unable to add humiliation. It might already exist."}), 400


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3000, debug=True)