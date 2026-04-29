# CDK DynamoDB API

REST API (API Gateway -> Lambda -> DynamoDB) deploy-ovan preko AWS CDK (Python).

## Arhitektura

```
Client  --HTTPS-->  API Gateway  -->  Lambda  -->  DynamoDB
                                         (boto3)
```

DynamoDB tabela `ItemsTable`:
- partition key: `PK` (string)
- sort key: `SK` (string)
- billing: PAY_PER_REQUEST (on-demand)
- bilo koji dodatni atributi se cuvaju (schemaless)

## Endpoints

| Metoda | Path                  | Opis                                       |
|--------|-----------------------|--------------------------------------------|
| POST   | `/items`              | Dodaje jedan item                          |
| GET    | `/items/{pk}/{sk}`    | Vraca jedan konkretan item                 |
| GET    | `/items/{pk}`         | Vraca celu particiju sa paginacijom        |

### POST /items
```json
{
  "PK": "USER#123",
  "SK": "ORDER#2025-01-01",
  "amount": 99.5,
  "status": "paid"
}
```

### GET /items/USER%23123/ORDER%232025-01-01
Vraca pojedinacan item. `#` se URL-enkoduje kao `%23`.

### GET /items/USER%23123?limit=20&nextToken=...
Vraca particiju. Response:
```json
{
  "items": [...],
  "count": 20,
  "nextToken": "eyJQS..."   // prosledi u sledecem zahtevu za sledecu stranu
}
```
Ako nema `nextToken` u response-u — nema vise podataka.

## Deploy

```bash
# 1. virtualenv + install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. CDK CLI (samo prvi put globalno)
npm install -g aws-cdk

# 3. bootstrap (samo prvi put po accountu/regionu)
cdk bootstrap

# 4. deploy
cdk deploy
```

Nakon deploy-a CDK ce ispisati URL API Gateway-a (npr.
`https://abc123.execute-api.eu-central-1.amazonaws.com/prod/`).

## Test (curl)

```bash
API="https://abc123.execute-api.eu-central-1.amazonaws.com/prod"

# POST
curl -X POST "$API/items" \
  -H "Content-Type: application/json" \
  -d '{"PK":"USER#1","SK":"ORDER#1","total":42}'

# GET jedan item
curl "$API/items/USER%231/ORDER%231"

# GET particiju sa paginacijom
curl "$API/items/USER%231?limit=10"
```

## Cleanup
```bash
cdk destroy
```
