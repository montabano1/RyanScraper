const config = {
    development: {
        apiBaseUrl: 'http://localhost:8080/api'
    },
    production: {
        apiBaseUrl: 'https://ryanscraper-production.up.railway.app/api'
    }
};

export const getApiBaseUrl = () => {
    const isProduction = process.env.NODE_ENV === 'production';
    return isProduction ? config.production.apiBaseUrl : config.development.apiBaseUrl;
};
