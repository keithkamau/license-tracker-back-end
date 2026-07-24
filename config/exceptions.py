from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """Custom exception handler for DRF."""
    response = exception_handler(exc, context)
    
    if response is not None:
        # Add status code to response
        response.data['status_code'] = response.status_code
        
        # Customize error messages
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            response.data['message'] = 'Invalid request. Please check your input.'
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            response.data['message'] = 'Authentication required.'
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            response.data['message'] = 'You do not have permission to perform this action.'
        elif response.status_code == status.HTTP_404_NOT_FOUND:
            response.data['message'] = 'The requested resource was not found.'
        elif response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            response.data['message'] = 'Too many requests. Please try again later.'
        elif response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            response.data['message'] = 'An internal server error occurred.'
    
    return response