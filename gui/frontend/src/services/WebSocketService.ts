class WebSocketServiceClass {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private messageHandlers: ((data: any) => void)[] = [];
  private clientId: string;
  private isConnected = false;
  private shouldReconnect = true;

  constructor() {
    this.clientId = this.generateClientId();
  }

  private generateClientId(): string {
    return `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  connect(url?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const wsUrl = url || `ws://localhost:8000/ws/${this.clientId}`;
      
      console.log(`Attempting to connect to WebSocket: ${wsUrl}`);
      
      try {
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = (event) => {
          console.log('WebSocket connected successfully');
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.shouldReconnect = true;
          
          // Send initial connection message
          this.send({
            type: 'connection',
            client_id: this.clientId,
            timestamp: new Date().toISOString(),
          });
          
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);
            
            // Call all registered message handlers
            this.messageHandlers.forEach(handler => {
              try {
                handler(data);
              } catch (error) {
                console.error('Error in WebSocket message handler:', error);
              }
            });
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket connection closed:', event.code, event.reason);
          this.isConnected = false;
          this.ws = null;
          
          // Attempt to reconnect if connection was not closed intentionally
          if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            
            setTimeout(() => {
              this.connect(wsUrl).catch(error => {
                console.error('Reconnection failed:', error);
              });
            }, this.reconnectDelay * this.reconnectAttempts);
          } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            reject(new Error('Max reconnection attempts reached'));
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          reject(error);
        };

      } catch (error) {
        console.error('Failed to create WebSocket connection:', error);
        reject(error);
      }
    });
  }

  disconnect(): void {
    console.log('Disconnecting WebSocket...');
    this.shouldReconnect = false;
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnecting');
      this.ws = null;
    }
    
    this.isConnected = false;
    this.reconnectAttempts = 0;
  }

  send(data: any): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket is not connected. Cannot send message:', data);
      return false;
    }

    try {
      this.ws.send(JSON.stringify(data));
      return true;
    } catch (error) {
      console.error('Error sending WebSocket message:', error);
      return false;
    }
  }

  onMessage(handler: (data: any) => void): void {
    this.messageHandlers.push(handler);
  }

  removeMessageHandler(handler: (data: any) => void): void {
    const index = this.messageHandlers.indexOf(handler);
    if (index !== -1) {
      this.messageHandlers.splice(index, 1);
    }
  }

  clearMessageHandlers(): void {
    this.messageHandlers = [];
  }

  getConnectionState(): string {
    if (!this.ws) return 'DISCONNECTED';
    
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'CONNECTING';
      case WebSocket.OPEN:
        return 'CONNECTED';
      case WebSocket.CLOSING:
        return 'CLOSING';
      case WebSocket.CLOSED:
        return 'CLOSED';
      default:
        return 'UNKNOWN';
    }
  }

  isConnectionOpen(): boolean {
    return this.isConnected && this.ws?.readyState === WebSocket.OPEN;
  }

  getClientId(): string {
    return this.clientId;
  }

  // Helper methods for common message types
  sendProgressUpdate(progress: number, message: string, status: string = 'running'): boolean {
    return this.send({
      type: 'progress_update',
      progress,
      message,
      status,
      timestamp: new Date().toISOString(),
    });
  }

  sendError(error: string): boolean {
    return this.send({
      type: 'error',
      message: error,
      timestamp: new Date().toISOString(),
    });
  }

  sendResult(result: any): boolean {
    return this.send({
      type: 'result',
      result,
      timestamp: new Date().toISOString(),
    });
  }

  sendStatusUpdate(status: string, data?: any): boolean {
    return this.send({
      type: 'status_update',
      status,
      data,
      timestamp: new Date().toISOString(),
    });
  }

  // Ping/Pong for connection health
  sendPing(): boolean {
    return this.send({
      type: 'ping',
      timestamp: new Date().toISOString(),
    });
  }

  // Auto-reconnect configuration
  setReconnectConfig(maxAttempts: number, delay: number): void {
    this.maxReconnectAttempts = maxAttempts;
    this.reconnectDelay = delay;
  }

  // Connection health check
  startHealthCheck(interval: number = 30000): void {
    setInterval(() => {
      if (this.isConnectionOpen()) {
        this.sendPing();
      }
    }, interval);
  }

  // Get connection statistics
  getConnectionStats(): any {
    return {
      clientId: this.clientId,
      isConnected: this.isConnected,
      connectionState: this.getConnectionState(),
      reconnectAttempts: this.reconnectAttempts,
      maxReconnectAttempts: this.maxReconnectAttempts,
      messageHandlers: this.messageHandlers.length,
    };
  }

  // Debug methods
  enableDebugLogging(): void {
    this.onMessage((data) => {
      console.log('[WebSocket Debug]', data);
    });
  }

  // Promise-based message waiting
  waitForMessage(
    predicate: (data: any) => boolean,
    timeout: number = 10000
  ): Promise<any> {
    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        this.removeMessageHandler(handler);
        reject(new Error('Message timeout'));
      }, timeout);

      const handler = (data: any) => {
        if (predicate(data)) {
          clearTimeout(timeoutId);
          this.removeMessageHandler(handler);
          resolve(data);
        }
      };

      this.onMessage(handler);
    });
  }

  // Subscribe to specific message types
  subscribeToMessageType(
    messageType: string,
    handler: (data: any) => void
  ): () => void {
    const wrappedHandler = (data: any) => {
      if (data.type === messageType) {
        handler(data);
      }
    };

    this.onMessage(wrappedHandler);

    // Return unsubscribe function
    return () => {
      this.removeMessageHandler(wrappedHandler);
    };
  }

  // Request-response pattern
  sendRequest(request: any, timeout: number = 5000): Promise<any> {
    const requestId = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const requestData = {
      ...request,
      request_id: requestId,
      type: 'request',
    };

    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        this.removeMessageHandler(handler);
        reject(new Error('Request timeout'));
      }, timeout);

      const handler = (data: any) => {
        if (data.type === 'response' && data.request_id === requestId) {
          clearTimeout(timeoutId);
          this.removeMessageHandler(handler);
          
          if (data.error) {
            reject(new Error(data.error));
          } else {
            resolve(data);
          }
        }
      };

      this.onMessage(handler);
      
      if (!this.send(requestData)) {
        clearTimeout(timeoutId);
        this.removeMessageHandler(handler);
        reject(new Error('Failed to send request'));
      }
    });
  }
}

// Export singleton instance
export const WebSocketService = new WebSocketServiceClass();