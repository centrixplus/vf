from odoo import models, fields, api
import requests
import logging
import json

_logger = logging.getLogger(__name__)

class OrdableAPI(models.AbstractModel):
    _name = 'ordable.api'
    _description = 'Ordable API Connector'

    def _get_config(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('ordable.base_url')
        token = self.env['ir.config_parameter'].sudo().get_param('ordable.api_token')
        return base_url, token

    def _push_to_ordable(self, payload, endpoint, method, brand):
        base_url = brand.ordable_base_url
        token = brand.ordable_api_token
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}/"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }

        try:
            data = json.loads(payload)
            category_name = data.get("name", "Unnamed")
            _logger.info(f"[ORDABLE] {method} {endpoint} '{category_name}' to {url} ...")
            if method=="DELETE":
                response = requests.request(method, url, headers=headers, timeout=15)
            else:
                response = requests.request(method, url, headers=headers, data=payload, timeout=15)
            status_code = response.status_code

            # Handle status codes
            if status_code not in (200, 201):
                _logger.warning(f"[ORDABLE] Failed ({status_code}) for '{category_name}': {response.text}")
                return {"error": f"HTTP {status_code}", "response": response.text}

            # Try to parse JSON safely
            try:
                response_data = response.json()
            except ValueError:
                _logger.warning(f"[ORDABLE] Non-JSON response for '{category_name}': {response.text}")
                return {"error": "Invalid JSON", "response": response.text}

            # Extract 'data' safely
            response_value = response_data.get("data")
            ordable_id = None

            # Handle different API response formats
            if isinstance(response_value, dict):
                ordable_id = response_value.get("id")
            elif isinstance(response_value, list) and response_value:
                ordable_id = response_value[0].get("id")

            if ordable_id:
                _logger.info(f"[ORDABLE] {endpoint} '{category_name}' '{method}' successfully with ID {ordable_id}.")
                return {"id": ordable_id, "response": response_data}
            else:
                _logger.warning(f"[ORDABLE] Success response but missing 'id' for '{category_name}': {response_data}")
                return {"warning": "Missing Ordable ID", "response": response_data}

        except requests.Timeout:
            _logger.error(f"[ORDABLE] Timeout while pushing {endpoint} to {url}")
            return {"error": "Timeout"}
        except requests.RequestException as e:
            _logger.exception(f"[ORDABLE] HTTP request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            _logger.exception(f"[ORDABLE] Unexpected error: {e}")
            return {"error": str(e)}

