import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
apiClient.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Response Error:', error);
    
    if (error.response?.status === 401) {
      // Handle unauthorized access
      console.error('Unauthorized access - license may be invalid');
    } else if (error.response?.status === 500) {
      // Handle server errors
      console.error('Server error occurred');
    }
    
    return Promise.reject(error);
  }
);

export class ApiService {
  // License Management
  static async validateLicense(licenseKey: string): Promise<any> {
    try {
      const response = await apiClient.post('/api/validate-license', {
        license_key: licenseKey,
      });
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'License validation failed');
    }
  }

  static async getLicenseStatus(): Promise<any> {
    try {
      const response = await apiClient.get('/api/license-status');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get license status');
    }
  }

  // Configuration Management
  static async getConfiguration(): Promise<any> {
    try {
      const response = await apiClient.get('/api/configuration');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get configuration');
    }
  }

  static async saveConfiguration(config: any): Promise<any> {
    try {
      const response = await apiClient.post('/api/configuration', config);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to save configuration');
    }
  }

  static async testConfiguration(config: any): Promise<any> {
    try {
      const response = await apiClient.post('/api/test-configuration', config);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Configuration test failed');
    }
  }

  // Automation Control
  static async startAutomation(config: any): Promise<any> {
    try {
      const response = await apiClient.post('/api/automation/start', config);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to start automation');
    }
  }

  static async stopAutomation(): Promise<any> {
    try {
      const response = await apiClient.post('/api/automation/stop');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to stop automation');
    }
  }

  static async runOffersOnly(config: any, headlessOffers: boolean = true): Promise<any> {
    try {
      const response = await apiClient.post('/api/automation/run-offers', {
        config: config,
        headless_offers: headlessOffers
      });
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to start offer agent');
    }
  }

  static async runConversationsOnly(config: any, headlessConversations: boolean = false): Promise<any> {
    try {
      const response = await apiClient.post('/api/automation/run-conversations', {
        config: config,  
        headless_conversations: headlessConversations
      });
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to start conversation agent');
    }
  }

  static async scrapeListingsOnly(searchTerm: string, config: any): Promise<any> {
    try {
      const response = await apiClient.post('/api/automation/scrape-listings', {
        search_term: searchTerm,
        config: config
      });
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to start listing scraper');
    }
  }

  // Negotiation Script Management
  static async getNegotiationScript(): Promise<any> {
    try {
      const response = await apiClient.get('/api/negotiation-script');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get negotiation script');
    }
  }

  static async saveNegotiationScript(content: string): Promise<any> {
    try {
      const response = await apiClient.post('/api/negotiation-script', {
        content: content
      });
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to save negotiation script');
    }
  }

  // Meetup Location Management
  static async getMeetupLocation(): Promise<any> {
    try {
      const response = await apiClient.get('/api/meetup-location');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get meetup location');
    }
  }

  static async saveMeetupLocation(location: string): Promise<any> {
    try {
      const response = await apiClient.post('/api/meetup-location', {
        location: location
      });
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to save meetup location');
    }
  }

  static async getAutomationStatus(): Promise<any> {
    try {
      const response = await apiClient.get('/api/automation/status');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get automation status');
    }
  }

  static async getAutomationResults(): Promise<any> {
    try {
      const response = await apiClient.get('/api/automation/results');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get automation results');
    }
  }

  // Detailed Data Methods for Modals
  static async getDetailedListings(): Promise<any> {
    try {
      const response = await apiClient.get('/api/detailed/listings');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get detailed listings');
    }
  }

  static async getDetailedOffers(): Promise<any> {
    try {
      const response = await apiClient.get('/api/detailed/offers');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get detailed offers');
    }
  }

  static async getDetailedNegotiations(): Promise<any> {
    try {
      const response = await apiClient.get('/api/detailed/negotiations');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get detailed negotiations');
    }
  }

  // Script Management
  static async getScriptStatus(): Promise<any> {
    try {
      const response = await apiClient.get('/api/scripts/status');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get script status');
    }
  }

  // Health Check
  static async healthCheck(): Promise<any> {
    try {
      const response = await apiClient.get('/api/health');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Health check failed');
    }
  }

  // Utility Methods
  static async downloadLogs(): Promise<Blob> {
    try {
      const response = await apiClient.get('/api/logs/download', {
        responseType: 'blob',
      });
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to download logs');
    }
  }

  static async exportConfiguration(): Promise<any> {
    try {
      const response = await apiClient.get('/api/configuration/export');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to export configuration');
    }
  }

  static async importConfiguration(configData: any): Promise<any> {
    try {
      const response = await apiClient.post('/api/configuration/import', configData);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to import configuration');
    }
  }

  // Statistics
  static async getStatistics(): Promise<any> {
    try {
      const response = await apiClient.get('/api/statistics');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get statistics');
    }
  }

  // Automation Progress Management
  static async getAutomationProgress(): Promise<any> {
    try {
      const response = await apiClient.get('/api/automation-progress');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get automation progress');
    }
  }

  static async resetAutomationProgress(): Promise<any> {
    try {
      const response = await apiClient.post('/api/reset-automation-progress');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to reset automation progress');
    }
  }

  // System Information
  static async getSystemInfo(): Promise<any> {
    try {
      const response = await apiClient.get('/api/system/info');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get system information');
    }
  }

  // Browser Management
  static async getBrowserStatus(): Promise<any> {
    try {
      const response = await apiClient.get('/api/browser/status');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get browser status');
    }
  }

  static async restartBrowser(): Promise<any> {
    try {
      const response = await apiClient.post('/api/browser/restart');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to restart browser');
    }
  }

  // Debug Methods
  static async getDebugInfo(): Promise<any> {
    try {
      const response = await apiClient.get('/api/debug/info');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to get debug information');
    }
  }

  static async clearCache(): Promise<any> {
    try {
      const response = await apiClient.post('/api/debug/clear-cache');
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to clear cache');
    }
  }

  // Notification methods for development
  static async sendTestNotification(message: string): Promise<any> {
    try {
      const response = await apiClient.post('/api/debug/test-notification', {
        message,
      });
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to send test notification');
    }
  }

  // File upload helper
  static async uploadFile(file: File, endpoint: string): Promise<any> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await apiClient.post(endpoint, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'File upload failed');
    }
  }

  // Conversation Actions
  static async sendFollowUp(messageId: string): Promise<any> {
    try {
      const response = await apiClient.post(`/api/conversations/${messageId}/follow-up`);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to send follow-up');
    }
  }

  static async closeConversation(messageId: string): Promise<any> {
    try {
      const response = await apiClient.post(`/api/conversations/${messageId}/close`);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to close conversation');
    }
  }

  // Helper method to check if backend is available
  static async isBackendAvailable(): Promise<boolean> {
    try {
      await this.healthCheck();
      return true;
    } catch (error) {
      return false;
    }
  }

  // Helper method to get API client for custom requests
  static getApiClient() {
    return apiClient;
  }
}