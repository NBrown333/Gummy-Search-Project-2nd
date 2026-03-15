"""
Flask web application for Gummy Bear Price Finder
Uses OpenStreetMap/Nominatim API instead of Google Maps
Python 3.9+ with type hints and modern standards
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import csv
import io
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from gummy_bear_finder import GummyBearFinder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize finder
finder = GummyBearFinder()


@app.route('/')
def index() -> str:
    """Render the main page"""
    return render_template('index.html')


@app.route('/api/search', methods=['POST'])
def search() -> tuple[Dict[str, Any], int]:
    """
    API endpoint for searching gummy bears
    
    Returns:
        JSON response with search results or error message
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request body'}), 400
        
        location = data.get('location', '').strip()
        distance = float(data.get('distance', 10))
        include_online = data.get('include_online', True)
        
        # Validate inputs
        if not location:
            return jsonify({'error': 'Location is required'}), 400
        
        if not (0 < distance <= 500):
            return jsonify({'error': 'Distance must be between 0 and 500 miles'}), 400
        
        logger.info(f"Search request: {location}, {distance} miles, include_online: {include_online}")
        
        # Find products
        products = finder.find_cheapest_gummy_bears(location, distance, include_online)
        
        # Convert to JSON-serializable format
        results = []
        for idx, product in enumerate(products[:50], 1):
            results.append({
                'rank': idx,
                'brand': product.brand,
                'name': product.name,
                'size_oz': product.size_oz,
                'price': round(product.price, 2),
                'shipping_cost': round(product.shipping_cost, 2),
                'total_cost': round(product.total_cost, 2),
                'cost_per_ounce': round(product.cost_per_ounce, 2),
                'store_name': product.store_name,
                'store_type': product.store_type.value,
                'distance_miles': round(product.distance_miles, 1) if product.distance_miles else None,
                'address': product.address or 'N/A',
                'url': product.url or '#',
                'artificial_ingredients': ', '.join(product.artificial_ingredients) or 'None'
            })
        
        logger.info(f"Found {len(results)} results")
        
        return jsonify({
            'success': True,
            'count': len(results),
            'location': location,
            'distance': distance,
            'include_online': include_online,
            'results': results,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        return jsonify({'error': f'Invalid input: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 500


@app.route('/api/export', methods=['POST'])
def export() -> tuple[Any, int, Dict]:
    """
    Export search results to CSV
    
    Returns:
        CSV file as attachment or error message
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request body'}), 400
        
        results = data.get('results', [])
        
        if not results:
            return jsonify({'error': 'No results to export'}), 400
        
        # Create CSV in memory
        output = io.StringIO()
        fieldnames = [
            'Rank', 'Brand', 'Name', 'Size (oz)', 'Price', 'Shipping',
            'Total Cost', 'Cost/oz', 'Store', 'Type', 'Distance (mi)',
            'Address', 'Artificial Ingredients'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in results:
            writer.writerow({
                'Rank': result['rank'],
                'Brand': result['brand'],
                'Name': result['name'],
                'Size (oz)': result['size_oz'],
                'Price': f"${result['price']:.2f}",
                'Shipping': f"${result['shipping_cost']:.2f}",
                'Total Cost': f"${result['total_cost']:.2f}",
                'Cost/oz': f"${result['cost_per_ounce']:.2f}",
                'Store': result['store_name'],
                'Type': result['store_type'],
                'Distance (mi)': result['distance_miles'] or 'Online',
                'Address': result['address'],
                'Artificial Ingredients': result['artificial_ingredients']
            })
        
        # Convert to bytes
        csv_bytes = io.BytesIO(output.getvalue().encode('utf-8'))
        csv_bytes.seek(0)
        
        logger.info(f"Exporting {len(results)} results to CSV")
        
        return send_file(
            csv_bytes,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'gummy_bear_prices_{datetime.now().strftime("%Y-%m-%d")}.csv'
        )
    
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return jsonify({'error': f'Export failed: {str(e)}'}), 500


@app.route('/api/health', methods=['GET'])
def health() -> tuple[Dict[str, Any], int]:
    """
    Health check endpoint
    
    Returns:
        JSON with health status
    """
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0',
        'api': 'OpenStreetMap/Nominatim',
        'description': 'No API keys required! Uses free OpenStreetMap data',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.errorhandler(404)
def not_found(error: Exception) -> tuple[Dict[str, str], int]:
    """Handle 404 errors"""
    logger.warning(f"404 error: {error}")
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error: Exception) -> tuple[Dict[str, str], int]:
    """Handle 500 errors"""
    logger.error(f"500 error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


@app.before_request
def log_request() -> None:
    """Log incoming requests"""
    logger.debug(f"{request.method} {request.path}")


@app.after_request
def log_response(response) -> Any:
    """Log outgoing responses"""
    logger.debug(f"Response: {response.status_code}")
    return response


if __name__ == '__main__':
    logger.info("Starting Gummy Bear Price Finder Flask app")
    app.run(debug=True, host='0.0.0.0', port=5000)
