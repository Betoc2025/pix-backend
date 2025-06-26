from flask import Blueprint, request, jsonify
import uuid
import datetime
import requests
import hashlib
import hmac
import json
from typing import Dict, Any

pix_bp = Blueprint('pix', __name__)

# Configurações fixas no código (seguro apenas se o repositório for privado)
PIX_API_URL = 'https://api.selfpaybr.com/functions/v1/transactions'
PIX_API_KEY = 'sk_live_wNIuLiybC8GzXsDdjYCDnyy9qmLO0hXOUh3Lxc8xiVZqnkPM'
WEBHOOK_SECRET = '6869a1a3-d56a-4714-967d-97bf32c4ebee'

class PixPaymentService:
    def create_pix_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self._validate_payment_data(payment_data)
            api_payload = self._prepare_api_payload(payment_data)

            headers = {
                'Authorization': PIX_API_KEY,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            response = requests.post(
                PIX_API_URL,
                json=api_payload,
                headers=headers,
                timeout=30
            )

            if response.status_code in [200, 201]:
                return self._format_response(response.json())
            else:
                raise Exception(f'Erro na API SelfPay: {response.status_code} - {response.text}')

        except Exception as e:
            raise Exception(f'Erro ao criar pagamento PIX: {str(e)}')

    def _validate_payment_data(self, data: Dict[str, Any]) -> None:
        required_fields = ['customer', 'items', 'amount']
        for field in required_fields:
            if field not in data:
                raise ValueError(f'Campo obrigatório ausente: {field}')

        customer = data['customer']
        for f in ['name', 'email', 'phone', 'document']:
            if f not in customer:
                raise ValueError(f'Campo customer.{f} é obrigatório')

        document = customer['document']
        if 'number' not in document or 'type' not in document:
            raise ValueError('Documento inválido')

        if not isinstance(data['items'], list) or not data['items']:
            raise ValueError('Items inválidos')

        if not isinstance(data['amount'], (int, float)) or data['amount'] <= 0:
            raise ValueError('Valor inválido')

    def _prepare_api_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "paymentMethod": "pix",
            "items": data["items"],
            "amount": int(data["amount"]),
            "customer": {
                "name": data["customer"]["name"],
                "email": data["customer"]["email"],
                "phone": data["customer"]["phone"],
                "document": {
                    "number": data["customer"]["document"]["number"],
                    "type": data["customer"]["document"]["type"].lower()
                }
            }
        }

    def _format_response(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": api_response.get("id"),
            "amount": api_response.get("amount"),
            "status": api_response.get("status"),
            "customer": api_response.get("customer"),
            "items": api_response.get("items"),
            "pix": {
                "qrcode": api_response["pix"]["qrcode"],
                "qrcode_image": None,
                "expirationDate": api_response["pix"]["expirationDate"]
            },
            "createdAt": api_response.get("createdAt")
        }

pix_service = PixPaymentService()

# ✅ Aqui aceita POST e OPTIONS (CORS total)
@pix_bp.route('/gerar-pix', methods=['POST', 'OPTIONS'])
def gerar_pix():
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type deve ser application/json'}), 400

        payment_data = request.get_json()
        result = pix_service.create_pix_payment(payment_data)
        return jsonify(result), 201

    except ValueError as e:
        return jsonify({'error': f'Dados inválidos: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@pix_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat(),
        'service': 'pix-backend'
    }), 200

@pix_bp.route('/webhook/pix', methods=['POST'])
def webhook_pix():
    try:
        signature = request.headers.get('X-Signature')
        if not signature:
            return jsonify({'error': 'Assinatura ausente'}), 401

        payload = request.get_data()
        expected_signature = hmac.new(
            WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return jsonify({'error': 'Assinatura inválida'}), 401

        webhook_data = request.get_json()
        print(f"Webhook recebido: {json.dumps(webhook_data, indent=2)}")
        return jsonify({'status': 'received'}), 200

    except Exception as e:
        return jsonify({'error': f'Erro no webhook: {str(e)}'}), 500
