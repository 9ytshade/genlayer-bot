const defaultApiUrl = 'http://127.0.0.1:8000';
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace('localhost', '127.0.0.1') || defaultApiUrl;
