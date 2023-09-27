#SPDX-License-Identifier: MIT
"""
Creates routes for user functionality
"""
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import logging
import requests
import os
import base64
import time
import secrets
import pandas as pd
from flask import request, Response, jsonify, session, render_template
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash
from sqlalchemy.sql import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from augur.application.db.session import DatabaseSession
from augur.tasks.github.util.github_task_session import GithubTaskSession
from augur.util.repo_load_controller import RepoLoadController
from augur.api.util import api_key_required, ssl_required

from augur.application.db.models import User, UserRepo, UserGroup, UserSessionToken, ClientApplication, RefreshToken
from augur.application.config import get_development_flag
from augur.tasks.init.redis_connection import redis_connection as redis
from ..server import app, engine

logger = logging.getLogger(__name__)
development = get_development_flag()
Session = sessionmaker(bind=engine)

from augur.api.routes import AUGUR_API_VERSION

AUGUR_API_VERSION = 'api/unstable'

def create_routes(server):

    @server.app.route('/{}/complexity/project_languages'.format(AUGUR_API_VERSION), methods=["GET"])
    def get_project_languages():


@app.route('/{}//generate_pdf/<name>'.format(AUGUR_API_VERSION), methods=["GET"])
    def generate_pdf(name):
        # Create a PDF file in memory
        pdf_buffer = io.BytesIO()
        p = canvas.Canvas(pdf_buffer, pagesize=letter)
        p.drawString(100, 750, f"Hello, {name}!")  # Customize the text with the parameter
        p.showPage()
        p.save()

        # Set up response to serve the PDF
        pdf_buffer.seek(0)
        response = Response(pdf_buffer.read())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename={name}.pdf'
        return response
