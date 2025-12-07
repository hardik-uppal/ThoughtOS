import os
import datetime
import plaid
from plaid.api import plaid_api
from plaid.configuration import Environment, Configuration
from plaid.api_client import ApiClient
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from dotenv import load_dotenv

load_dotenv()

PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
PLAID_ENV = os.getenv('PLAID_ENV', 'sandbox')

def get_plaid_client():
    if not PLAID_CLIENT_ID or not PLAID_SECRET:
        return None
    
    host = Environment.Sandbox
    if PLAID_ENV == 'development':
        host = Environment.Development
    elif PLAID_ENV == 'production':
        host = Environment.Production

    configuration = Configuration(
        host=host,
        api_key={
            'clientId': PLAID_CLIENT_ID,
            'secret': PLAID_SECRET,
        }
    )
    api_client = ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)

def create_link_token():
    client = get_plaid_client()
    if not client:
        return {"error": "Missing Plaid Credentials"}

    request = LinkTokenCreateRequest(
        products=[Products('transactions')],
        client_name="ContextOS",
        country_codes=[CountryCode('US'), CountryCode('CA')],
        language='en',
        user=LinkTokenCreateRequestUser(
            client_user_id=str(datetime.datetime.now().timestamp())
        )
    )
    response = client.link_token_create(request)
    return response.to_dict()

def exchange_public_token(public_token):
    client = get_plaid_client()
    request = ItemPublicTokenExchangeRequest(
        public_token=public_token
    )
    response = client.item_public_token_exchange(request)
    return response['access_token']

def fetch_transactions(access_token, days=30, start_date=None, end_date=None):
    client = get_plaid_client()
    
    if not start_date:
        start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).date()
    if not end_date:
        end_date = datetime.datetime.now().date()
    
    # Pagination Loop
    all_transactions = []
    offset = 0
    count = 500 # Max allowed by Plaid
    
    while True:
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options={
                "count": count,
                "offset": offset
            }
        )
        
        try:
            response = client.transactions_get(request)
            transactions = response['transactions']
            all_transactions.extend(transactions)
            
            # Check if we need to fetch more
            total_transactions = response['total_transactions']
            if len(all_transactions) >= total_transactions or len(transactions) == 0:
                break
                
            offset += len(transactions)
            
        except plaid.ApiException as e:
            print(f"Plaid API Error: {e}")
            break
    
    # Simplify for our graph
    simplified_txns = []
    for t in all_transactions:
        simplified_txns.append({
            "id": t['transaction_id'],
            "merchant": t['merchant_name'] or t['name'],
            "amount": t['amount'],
            "category": t['category'][0] if t['category'] else "Uncategorized",
            "date": str(t['date'])
        })
        
    return simplified_txns
