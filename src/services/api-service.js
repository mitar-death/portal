/**
 * API Service - Centralized management of API URLs
 * 
 * This service provides a consistent way to access API URLs throughout the application.
 * It uses environment variables to determine the correct base URL.
 */

// Function to determine the correct API URL based on environment
const getApiUrl = () => {
    // Check if we're in production environment
    const isProduction = process.env.NODE_ENV === 'production';
    let url;

    if (isProduction) {
        // Use development URL in production (as per requirement)
        url = process.env.VUE_APP_DEV_BASE_URL;
    } else {
        // Use production URL in development (as per requirement)
        url = process.env.VUE_APP_PROD_BASE_URL;
    }

    // If neither environment variable is set, fall back to the legacy API_BASE_URL or default
    if (!url) {
        url = process.env.VUE_APP_API_BASE_URL || process.env.VUE_APP_API_URL || '/api';
    }

    console.log(`API URL determined: ${url} (Environment: ${process.env.NODE_ENV})`);
    return url;
};

// Export a singleton instance of the API URL
export const apiUrl = getApiUrl();

// For debugging
console.log(`API Service initialized with URL: ${apiUrl} (Environment: ${process.env.NODE_ENV})`);

export default {
    getApiUrl,
    apiUrl
};
