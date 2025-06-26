from flask import Blueprint, request, jsonify
import uuid
import datetime
import os
import requests
import hashlib
import hmac
import json
from typing import Dict, Any

pix_bp = Blueprint('pix', __name__)

# Configurações PIX (devem ser variáveis de ambiente em produção)
PIX_API_URL = os.getenv('PIX_API_URL', 'https://api.selfpay.com.br/v1')
PIX_API_KEY = os.getenv('PIX_API_KEY', 'sua_api_key_aqui')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'seu_webhook_secret_aqui')

class PixPaymentService:
    """Serviço para integração com API PIX"""

    def __init__(self):
        self.api_url = PIX_API_URL
        self.api_key = PIX_API_KEY

    def create_pix_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um pagamento PIX"""
        try:
            self._validate_payment_data(payment_data)
            api_payload = self._prepare_api_payload(payment_data)

            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.post(
                f'{self.api_url}/payments',
                json=api_payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 201:
                return self._format_response(response.json())
            else:
                raise Exception(f'Erro na API PIX: {response.status_code} - {response.text}')

        except Exception as e:
            raise Exception(f'Erro ao criar pagamento PIX: {str(e)}')

    def check_payment_status(self, transaction_id: str) -> Dict[str, Any]:
        """Verifica o status de um pagamento PIX"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                f'{self.api_url}/payments/{transaction_id}',
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f'Erro ao verificar status: {response.status_code}')

        except Exception as e:
            raise Exception(f'Erro ao verificar status do pagamento: {str(e)}')

    def _validate_payment_data(self, data: Dict[str, Any]) -> None:
        required_fields = ['customer', 'items', 'amount']
        for field in required_fields:
            if field not in data:
                raise ValueError(f'Campo obrigatório ausente: {field}')

        customer = data['customer']
        customer_required = ['name', 'email', 'phone', 'document']
        for field in customer_required:
            if field not in customer:
                raise ValueError(f'Campo customer.{field} é obrigatório')

        if 'number' not in customer['document'] or 'type' not in customer['document']:
            raise ValueError('Documento deve conter number e type')

        if not isinstance(data['items'], list) or len(data['items']) == 0:
            raise ValueError('Items deve ser uma lista não vazia')

        if not isinstance(data['amount'], (int, float)) or data['amount'] <= 0:
            raise ValueError('Amount deve ser um número positivo')

    def _prepare_api_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        transaction_id = str(uuid.uuid4())
        expiration_date = datetime.datetime.now() + datetime.timedelta(minutes=30)

        return {
            'external_id': transaction_id,
            'amount': int(data['amount']),
            'description': f'Pagamento Beto Carrero - {transaction_id[:8]}',
            'customer': {
                'name': data['customer']['name'],
                'email': data['customer']['email'],
                'phone': data['customer']['phone'],
                'document': {
                    'type': data['customer']['document']['type'],
                    'number': data['customer']['document']['number']
                }
            },
            'items': data['items'],
            'expires_at': expiration_date.isoformat(),
            'notification_url': f'{request.host_url}webhook/pix'
        }

    def _format_response(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'id': api_response.get('id'),
            'external_id': api_response.get('external_id'),
            'status': api_response.get('status', 'waiting_payment'),
            'amount': api_response.get('amount'),
            'customer': api_response.get('customer'),
            'items': api_response.get('items'),
            'pix': {
                'qrcode': api_response.get('pix', {}).get('qrcode'),
                'qrcode_image': api_response.get('pix', {}).get('qrCodeUrl'),
                'expirationDate': api_response.get('pix', {}).get('expirationDate')
            },
            'createdAt': api_response.get('createdAt', datetime.datetime.now().isoformat())
        }

pix_service = PixPaymentService()

@pix_bp.route('/gerar-pix', methods=['POST'])
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

@pix_bp.route('/status/<transaction_id>', methods=['GET'])
def verificar_status(transaction_id):
    try:
        result = pix_service.check_payment_status(transaction_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao verificar status: {str(e)}'}), 500

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

@pix_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat(),
        'service': 'pix-backend'
    }), 200
