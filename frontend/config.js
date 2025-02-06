const config = {
    development: {
        apiBaseUrl: 'http://localhost:5000/api'
    },
    production: {
        // Change this to your hosted backend URL when deployed
        apiBaseUrl: process.env.REACT_APP_API_URL || 'https://ryan-scraper-xxxxx.ondigitalocean.app/api'  // You'll get this URL from doctl apps list
    }
};

export const getApiBaseUrl = () => {
    const isProduction = process.env.NODE_ENV === 'production';
    return isProduction ? config.production.apiBaseUrl : config.development.apiBaseUrl;
};
