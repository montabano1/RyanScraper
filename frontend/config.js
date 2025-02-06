const config = {
    development: {
        apiBaseUrl: 'http://localhost:8080/api'
    },
    production: {
        // In production, use relative path since frontend and backend are served from the same domain
        apiBaseUrl: '/api'
    }
};

export const getApiBaseUrl = () => {
    // Use import.meta.env for Vite
    const isProduction = import.meta.env.PROD;
    return isProduction ? config.production.apiBaseUrl : config.development.apiBaseUrl;
};

// Helper function to construct API URLs
export const getApiUrl = (endpoint) => {
    const baseUrl = getApiBaseUrl();
    return `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
};
