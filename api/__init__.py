import pathlib
import random
import resend
from IPython.display import Markdown
from IPython.display import display
import os
import google.generativeai as genai
from dotenv import load_dotenv
import textwrap
from flask import Flask, request, jsonify, send_file
from flask_restx import Namespace, Resource, fields, Api, reqparse
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, JWTManager
from flask import request
from .utils import db
from .models.user import User
from flask_cors import CORS
from pdfminer.high_level import extract_text
from http import HTTPStatus
from datetime import timedelta
from flask_migrate import Migrate
from pathlib import Path

# python txt2speech lib
import pyttsx3
from gtts import gTTS

from io import BytesIO

load_dotenv()

google_key = os.getenv('GOOGLE_API_KEY')


'''
    file uploader arguments
'''
file_upload_parser = reqparse.RequestParser()
file_upload_parser.add_argument(
    'file', type='werkzeug.datastructures.FileStorage', location='files', required=True, help='PDF File')


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = '123jb_gejdgajsaj00saj'
    app.config['SQLALCHEMY_TRACK_MODIFICATION'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///aidatabase.db'
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(minutes=60)
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=30)
    CORS(app)

    db.init_app(app)
    with app.app_context():
        db.create_all()
    JWTManager(app)
    Migrate(app, db)

    engine = pyttsx3.init()

    api = Api(app, title="Gemini Backend Sample", version=1.0)

    propmt_namespace = Namespace(
        'prompt', description='Namespace for prompting')
    question_model = propmt_namespace.model('Prompt', {
        'prompt': fields.String(required=True, description='prompt field')
    })

    pdf_namespace = Namespace(
        'PDF', description="Namespace and logic for summarize pdf")

    def to_markdown(text):
        text = text.replace('•', '  *')
        return Markdown(textwrap.indent(text, '> ', predicate=lambda _: True))

    genai.configure(api_key=google_key)

    auth_namespace = Namespace('Authentication', description="Auth namespace")
    signup_model = auth_namespace.model('SignUp', {
        'id': fields.Integer(description='ID for users'),
        'fullname': fields.String(description='User fullname', required=True),
        'email': fields.String(description='User email', required=True),
        'password': fields.String(description='User password', required=True),
    })
    verify_model = auth_namespace.model('Verify', {
        'email': fields.String(description='User email', required=True),
        'code': fields.String(description='User verification code', required=True)
    })
    verify_resend = auth_namespace.model('rESEND', {
        'email': fields.String(description='User email', required=True),
    })
    login_model = auth_namespace.model('Login', {
        'email': fields.String(description='User email', required=True),
        'password': fields.String(description='User password', required=True),
    })
    saved_model = auth_namespace.model('savedUser', {
        'id': fields.Integer(description='ID for users'),
        'fullname': fields.String(description='User fullname', required=True),
        'email': fields.String(description='User email', required=True),
        'password': fields.String(description='User password', required=True),
        'code': fields.String(description='User code', required=True),
    })

    audio_model = propmt_namespace.model('audio', {
        'text': fields.String(description='User input text', required=True),
    })

    resend.api_key = os.getenv('RESEND_API_KEY')

    @auth_namespace.route('/signup')
    class SignUp(Resource):
        @auth_namespace.expect(signup_model)
        @auth_namespace.marshal_with(signup_model)
        def post(self):
            '''
            Register a new user
            '''
            data = request.get_json()
            fullname = data['fullname']
            email = data['email']
            password = generate_password_hash(data['password'])
            code = str(random.randint(1000, 9999))

            save_user = User(
                fullname=fullname, email=email, password=password, code=code)
            print(code)
            save_user.save()

            params: resend.Emails.SendParams = {
                "from": "onboarding@resend.dev",
                "to": [email],
                "subject": "Verify your email",
                "html": "<p>Hello {},</p><p>This is your verification code: {}</p> <p>Thank you, <br/>DelveAi Team.</p>".format(fullname, code),
            }

            r = resend.Emails.send(params)

            return save_user, HTTPStatus.CREATED

    @auth_namespace.route('/verify')
    class VerifyUserCode(Resource):
        @auth_namespace.expect(verify_model)
        def post(self):
            '''
                Verify user code
            '''

            data = request.get_json()
            email = data['email']
            code = data['code']

            user = User.query.filter_by(email=email).first()
            if code == user.code:
                response = {
                    "message": "user successfully verified"
                }

                return response, HTTPStatus.OK
            else:
                response = {
                    "message": "check verification code again."
                }

                return response, HTTPStatus.FORBIDDEN

    @auth_namespace.route('/resend_code')
    class VerifyUserCode(Resource):
        @auth_namespace.expect(verify_resend)
        def put(self):
            '''
                Resend user code
            '''

            data = request.get_json()
            email = data['email']
            code = str(random.randint(1000, 9999))

            user = User.query.filter_by(email=email).first()
            user.code = code
            print(code)

            db.session.commit()

            response = {
                "message": "user code sent to {}".format(email)
            }

            params: resend.Emails.SendParams = {
                "from": "onboarding@resend.dev",
                "to": [email],
                "subject": "Verify your email",
                "html": "<p>Hello {},</p><p>This is your new verification code: {}</p> <p>Thank you, <br/>DelveAi Team.</p>".format(user.fullname, code),
            }

            r = resend.Emails.send(params)

            return response, HTTPStatus.OK

    @auth_namespace.route('/login')
    class Login(Resource):
        @auth_namespace.expect(login_model)
        def post(self):
            '''
            Generate a jwt tokens for user to login
            '''

            data = request.get_json()
            email = data['email']
            password = data['password']

            user = User.query.filter_by(email=email).first()
            if (user is not None) and (check_password_hash(user.password, password)):
                access_token = create_access_token(identity=email)
                refresh_token = create_refresh_token(identity=email)

                response = {
                    "access_token": access_token,
                    'refresh_token': refresh_token
                }

                return response, HTTPStatus.OK
            else:
                response = {
                    "message": 'Check password or email again. Invalid credentials'
                }

                return response, HTTPStatus.FORBIDDEN

    @auth_namespace.route('/refresh_token')
    class RefreshToken(Resource):
        @jwt_required(refresh=True)
        def get(self):
            '''
            Refresh user token
            '''

            current_user = get_jwt_identity()
            user = User.query.filter_by(email=current_user).first()

            if user:
                access_token = create_access_token(identity=current_user)
                refresh_token = create_refresh_token(identity=current_user)

                response = {
                    "access_token": access_token,
                    'refresh_token': refresh_token
                }

                return response, HTTPStatus.OK

            else:
                response = {
                    "message": "Error providing refresh tokens"
                }

                return response, HTTPStatus.FORBIDDEN

    @propmt_namespace.route('/prompt')
    class PromptResource(Resource):
        @propmt_namespace.expect(question_model)
        def post(self):
            '''
                prompt to gemini resources
            '''

            data = request.get_json()
            user_input = data['prompt']

            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    print(m.name)

            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(f"{user_input}")
            to_markdown(response.text)

            if response.text:
                return response.text, 200
            else:
                response = {
                    "message": "Server error"
                }

                return response, 401

    def get_downloads_folder():
        # Cross-platform way to get the Downloads folder
        return os.path.join(Path.home(), 'Downloads')

    @propmt_namespace.route('/save-audio')
    class DownloadTextToAudio(Resource):
        @propmt_namespace.expect(audio_model)
        def post(self):
            data = request.get_json()
            text = data['text']

            downloads_folder = get_downloads_folder()
            if not os.path.exists(downloads_folder):
                os.makedirs(downloads_folder)
            filename = os.path.join(downloads_folder, "output.mp3")

            tts = gTTS(text=text, lang='en')
            tts.save(filename)

            return send_file(filename, as_attachment=True)

    @pdf_namespace.route('/pdf_interaction')
    class PDFInteraction(Resource):
        def post(self):
            '''
                Route to extract text from pdf and request to AI
            '''
            uploaded_file = request.files['file']
            user_data = request.form.get('text')

            if uploaded_file and uploaded_file.filename.endswith('.pdf'):
                pdf_stream = BytesIO(uploaded_file.read())
                extracted_text = extract_text(pdf_stream)

                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        print(m.name)

                print(f"{user_data}: {extracted_text[:500]}")

                model = genai.GenerativeModel('gemini-pro')
                text_length = len(extracted_text)
                if text_length >= 20000:
                    response = model.generate_content(
                        f"{user_data}: {extracted_text}")
                    # f"{user_data}: {extracted_text[:20000]}")
                else:
                    response = model.generate_content(
                        f"{user_data}: {extracted_text}")
                to_markdown(response.text)

                if response.text:
                    return response.text, 200
                else:
                    response = {
                        "message": "Server error"
                    }

                    return response, 401

    api.add_namespace(auth_namespace, path='/auth')
    api.add_namespace(propmt_namespace, path='/ai')
    api.add_namespace(pdf_namespace, path='/pdf')
    return app
