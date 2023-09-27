#SPDX-License-Identifier: MIT
"""
Creates routes for user functionality
"""
import base64
from augur.api.metrics.repo_meta import license_files
from augur.api.metrics.insight import top_insights
from augur.api.routes import AUGUR_API_VERSION
from ..server import app, route_transform
import sqlalchemy as s
import pandas as pd
from augur.api.util import metric_metadata
import os
import requests
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from flask import request, Response, jsonify, session, render_template
from augur.api.metrics.repo_meta import license_files
from augur.api.metrics.insight import top_insights
from augur.api.routes import AUGUR_API_VERSION

AUGUR_API_VERSION = 'api/unstable'

@app.route('/{}/generate_pdf/<name>'.format(AUGUR_API_VERSION))
def generate_pdf(name):
    # Create a PDF file in memory
    pdf_buffer = io.BytesIO()
    p = canvas.Canvas(pdf_buffer, pagesize=letter)
    p.drawString(100, 750, f"Hello, {name}!")  # Customize the text with the parameter
    p.showPage()
    p.save()
    pdf_buffer.seek(0)
    response = Response(pdf_buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={name}.pdf'
    return response
