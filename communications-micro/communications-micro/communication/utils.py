from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from django.conf import settings
from django.core.management import call_command   # ✅ for migrate command
from django.db import connections                 # ✅ for DB connections
from io import StringIO                           # ✅ StringIO for capturing command output
import os                                         # ✅ for os.getenv
import logging                                    # ✅ for logger

# Import ensure_alias_for_client from its module
from softservice.db_utils import ensure_alias_for_client  # Update the import path as needed

# setup logger
logger = logging.getLogger(_name_)

class RegisterDBByClientAPIView(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [JSONParser]

    def post(self, request):
        client_id = (request.data or {}).get("client_id")
        client_username = (request.data or {}).get("client_username")

        if not client_id and not client_username:
            return Response({"detail": "Provide client_id or client_username."}, status=400)

        try:
            alias = ensure_alias_for_client(
                client_id=int(client_id) if str(client_id).isdigit() else None,
                client_username=client_username if not client_id else None,
            )

            # Run migration automatically if DEBUG or env set
            if settings.DEBUG or str(os.getenv("ASSET_AUTO_MIGRATE", "0")) == "1":
                out = StringIO()
                call_command(
                    "migrate", "api", database=alias,
                    interactive=False, verbosity=1, stdout=out
                )
                logger.info("Migrated app 'api' on %s\n%s", alias, out.getvalue())

            # Close connection after migration
            try:
                connections[alias].close()
            except Exception:
                pass

            return Response({"detail": "Alias ready", "alias": alias}, status=201)

        except Exception as e:
            logger.exception("RegisterDBByClient failed")
            return Response({"detail": str(e)}, status=400)