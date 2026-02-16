from aws_lambda import lambda_handler
import json

# Standard API Gateway Lambda proxy integration event structure
# Body is at top level as a JSON string
test_event = {
    "httpMethod": "POST",
    "path": "/webhook",
    "body": json.dumps({
        "update_id": 788190251,
        "message": {
            "message_id": 1333,
            "from": {
                "id": 87575599,
                "is_bot": False,
                "first_name": "N",
                "last_name": "A",
                "username": "nainarora",
                "language_code": "en"
            },
            "chat": {
                "id": 427988146,
                "first_name": "N",
                "last_name": "A",
                "username": "nainarora",
                "type": "private"
            },
            "date": 1633935457,
            "text": "/get_latest",
            "entities": [
                {
                    "offset": 0,
                    "length": 5,
                    "type": "bot_command"
                }
            ]
        }
    }),
    "requestContext": {
        "path": "/webhook",
        "requestId": "test-request-id",
        "httpMethod": "POST"
    }
}

# Test the lambda handler
result = lambda_handler(test_event, {})
print(json.dumps(result, indent=2))


