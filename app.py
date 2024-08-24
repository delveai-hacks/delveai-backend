import pathlib
from IPython.display import Markdown
from IPython.display import display
import os
import google.generativeai as genai
from dotenv import load_dotenv
import textwrap
from flask import Flask, request, jsonify
from flask_restx import Namespace, Resource, fields, Api, reqparse
from flask_cors import CORS
from pdfminer.high_level import extract_text
from http import HTTPStatus

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
    CORS(app)
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

    @pdf_namespace.route('/pdf_summarize')
    class PDFSummarize(Resource):
        def post(self):
            '''
                Route to extract text from pdf and request to AI
            '''
            uploaded_file = request.files['file']

            if uploaded_file and uploaded_file.filename.endswith('.pdf'):
                pdf_stream = BytesIO(uploaded_file.read())
                extracted_text = extract_text(pdf_stream)

                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        print(m.name)

                print(f"Summarize: {extracted_text[:500]}")

                model = genai.GenerativeModel('gemini-pro')
                text_length = len(extracted_text)
                if text_length >= 20000:
                    response = model.generate_content(
                        f"Summarize: {extracted_text[:20000]}")
                else:
                    response = model.generate_content(
                        f"Summarize: {extracted_text}")
                to_markdown(response.text)

                if response.text:
                    return response.text, 200
                else:
                    response = {
                        "message": "Server error"
                    }

                    return response, 401

    api.add_namespace(propmt_namespace, path='/ai')
    api.add_namespace(pdf_namespace, path='/pdf')
    return app
