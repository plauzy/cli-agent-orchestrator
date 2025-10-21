"""
Lambda handler for CAO API Gateway integration.
This is a simplified version - in production, you would integrate with your actual backend.
"""
import json
import os
import boto3
from typing import Any, Dict

dynamodb = boto3.resource('dynamodb')
terminal_table = dynamodb.Table(os.environ['TERMINAL_TABLE_NAME'])
session_table = dynamodb.Table(os.environ['SESSION_TABLE_NAME'])


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for API Gateway proxy integration.
    Routes requests to appropriate handlers based on path and method.
    """
    print(f"Event: {json.dumps(event)}")

    path = event.get('path', '')
    method = event.get('httpMethod', '')

    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }

    try:
        # Route to appropriate handler
        if path == '/sessions' and method == 'GET':
            return list_sessions(headers)
        elif path == '/sessions' and method == 'POST':
            return create_session(event, headers)
        elif path.startswith('/sessions/') and method == 'GET':
            session_id = path.split('/')[-1]
            return get_session(session_id, headers)
        elif path.startswith('/sessions/') and method == 'DELETE':
            session_id = path.split('/')[-1]
            return delete_session(session_id, headers)
        elif 'terminals' in path and method == 'GET':
            if path.count('/') == 2:  # /terminals/{id}
                terminal_id = path.split('/')[-1]
                return get_terminal(terminal_id, headers)
            else:  # /sessions/{id}/terminals
                return list_terminals(headers)
        else:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'Not found'})
            }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }


def list_sessions(headers: Dict[str, str]) -> Dict[str, Any]:
    """List all sessions."""
    response = session_table.scan()
    sessions = response.get('Items', [])

    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps(sessions, default=str)
    }


def create_session(event: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    """Create a new session."""
    import uuid
    from datetime import datetime

    body = json.loads(event.get('body', '{}'))
    session_id = str(uuid.uuid4())

    session = {
        'id': session_id,
        'name': body.get('name', f'session-{session_id[:8]}'),
        'created_at': datetime.utcnow().isoformat(),
        'terminals': []
    }

    session_table.put_item(Item=session)

    return {
        'statusCode': 201,
        'headers': headers,
        'body': json.dumps(session, default=str)
    }


def get_session(session_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Get a specific session."""
    response = session_table.get_item(Key={'id': session_id})
    session = response.get('Item')

    if not session:
        return {
            'statusCode': 404,
            'headers': headers,
            'body': json.dumps({'error': 'Session not found'})
        }

    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps(session, default=str)
    }


def delete_session(session_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Delete a session."""
    session_table.delete_item(Key={'id': session_id})

    return {
        'statusCode': 204,
        'headers': headers,
        'body': ''
    }


def list_terminals(headers: Dict[str, str]) -> Dict[str, Any]:
    """List all terminals."""
    response = terminal_table.scan()
    terminals = response.get('Items', [])

    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps(terminals, default=str)
    }


def get_terminal(terminal_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Get a specific terminal."""
    response = terminal_table.get_item(Key={'id': terminal_id})
    terminal = response.get('Item')

    if not terminal:
        return {
            'statusCode': 404,
            'headers': headers,
            'body': json.dumps({'error': 'Terminal not found'})
        }

    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps(terminal, default=str)
    }
