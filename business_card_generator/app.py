import identity.web
import mimetypes
import os

from http import HTTPStatus
from typing import Optional
from flask import Blueprint, Flask, abort, redirect, render_template, request, session, send_file, url_for
from flask_session import Session
from pydantic import ValidationError
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.wrappers import Response
from whitenoise import WhiteNoise

from . import __about__
from .card import CardParams, MeCard, VCard
from .settings import Settings


# ------------------------------------------------------------------------------

# Environment variables
AUTHORITY = os.getenv("OAUTH_AUTHORITY")
SCOPE = []

# if SUBFOLDER_PATH does not exist as an environment variable, set it to a static value
if not os.getenv("SUBFOLDER_PATH"):
    SUBFOLDER_PATH = os.getenv("SUBFOLDER_PATH")
else:
    SUBFOLDER_PATH = "/en/emea/cema/business-card-generator"

# Application (client) ID of app registration
CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
# Application's generated client secret: never check this into source control!
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
 
REDIRECT_PATH = os.getenv("OAUTH_REDIRECT_PATH")  # Used for forming an absolute URL to your redirect URI.

# ------------------------------------------------------------------------------

views_bp = Blueprint("views", __name__)

auth = identity.web.Auth(
    session=session,
    authority=AUTHORITY,
    client_id=CLIENT_ID,
    client_credential=CLIENT_SECRET,
)


def card_params_from_args() -> CardParams:
    try:
        return CardParams(**request.args.to_dict())
    except ValidationError:
        abort(HTTPStatus.UNPROCESSABLE_ENTITY)


@views_bp.get("/")
@views_bp.get(SUBFOLDER_PATH + "/")
def get_home() -> str:
    if not auth.get_user():
        auth_endpoint = auth.log_in(
            scopes=SCOPE, # Have user consent to scopes during log-in
            redirect_uri=url_for("views.auth_response", _external=True), # Optional. If present, this absolute URL must match your app's redirect_uri registered in Microsoft Entra admin center
        )
        return redirect(auth_endpoint["auth_uri"])
    return render_template("home.html")


@views_bp.get("/card")
@views_bp.get(SUBFOLDER_PATH + "/card")
def get_card() -> str:
    return render_template("card.html")


@views_bp.get("/vcard.svg")
@views_bp.get(SUBFOLDER_PATH + "/vcard.svg")
def get_vcard_svg() -> Response:
    card_params = card_params_from_args()
    vcard = VCard(card_params)
    return send_file(
        vcard.qrcode_svg(),
        mimetype=mimetypes.types_map[".svg"],
        download_name="vcard.svg",
    )


@views_bp.get("/vcard.png")
@views_bp.get(SUBFOLDER_PATH + "/vcard.png")
def get_vcard_png() -> Response:
    card_params = card_params_from_args()
    vcard = VCard(card_params)
    return send_file(
        vcard.qrcode_png(),
        mimetype=mimetypes.types_map[".png"],
        download_name="vcard.png",
    )


@views_bp.get("/vcard.vcf")
@views_bp.get(SUBFOLDER_PATH + "/vcard.vcf")
def get_vcard_vcf() -> Response:
    card_params = card_params_from_args()
    vcard = VCard(card_params)
    return send_file(
        vcard.vcf(),
        mimetype=mimetypes.types_map[".vcf"],
        download_name="vcard.vcf",
    )


@views_bp.get("/mecard.svg")
@views_bp.get(SUBFOLDER_PATH + "/mecard.svg")
def get_mecard_svg() -> Response:
    card_params = card_params_from_args()
    mecard = MeCard(card_params)
    return send_file(
        mecard.qrcode_svg(),
        mimetype=mimetypes.types_map[".svg"],
        download_name="mecard.svg",
    )


@views_bp.get("/mecard.png")
@views_bp.get(SUBFOLDER_PATH + "/mecard.png")
def get_mecard_png() -> Response:
    card_params = card_params_from_args()
    mecard = MeCard(card_params)
    return send_file(
        mecard.qrcode_png(),
        mimetype=mimetypes.types_map[".png"],
        download_name="mecard.png",
    )


@views_bp.get("/mecard.vcf")
@views_bp.get(SUBFOLDER_PATH + "/mecard.vcf")
def get_mecard_vcf() -> Response:
    card_params = card_params_from_args()
    mecard = MeCard(card_params)
    return send_file(
        mecard.vcf(),
        mimetype=mimetypes.types_map[".vcf"],
        download_name="mecard.vcf",
    )


@views_bp.get(REDIRECT_PATH)
def auth_response():
    result = auth.complete_log_in(request.args)
    if "error" in result:
        return render_template("auth_error.html", result=result)
    return redirect(url_for("views.get_home"))


@views_bp.get("/auth_error")
def auth_error():
    return render_template("auth_error.html")

@views_bp.get("/logout")
@views_bp.get(SUBFOLDER_PATH + "/logout")
def logout():
    return redirect(auth.log_out(url_for("views.get_home", _external=True)))

# ------------------------------------------------------------------------------


def create_app(env_file: Optional[str] = ".env") -> Flask:
    settings = Settings(_env_file=env_file)  # type: ignore[call-arg]

    app = Flask(__name__)
    app.config.from_object(settings)
    app.config["about"] = dict(
        name=__about__.__name__,
        description=__about__.__description__,
        version=__about__.__version__,
    )
    app.debug = settings.app_environment == "development"
    app.testing = settings.app_environment == "testing"

    app.wsgi_app = WhiteNoise(  # type: ignore[method-assign]
        app.wsgi_app,
        root=app.static_folder,
        prefix=app.static_url_path,
        autorefresh=app.debug,
    )
    app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
        app.wsgi_app, x_proto=1, x_host=1
    )

    @app.before_request
    def _force_https() -> Optional[Response]:
        if settings.force_https and request.url.startswith("http://"):
            https_url = request.url.replace("http://", "https://", 1)
            return redirect(https_url)
        return None

    app.register_blueprint(views_bp, url_prefix="")

    # Tells the Flask-session extension to store sessions in the filesystem
    app.config['SESSION_TYPE'] = 'filesystem'
    app.secret_key = app.config['SECRET_KEY']
    Session(app)

    return app
