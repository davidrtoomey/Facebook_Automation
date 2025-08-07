import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Alert,
  Paper,
  Grid,
  Divider,
  Card,
  CardContent,
  CircularProgress,
} from '@mui/material';
import { VpnKey, Check } from '@mui/icons-material';
import { ApiService } from '../services/ApiService';

interface LicenseFormProps {
  onLicenseValidated: (licenseInfo: any) => void;
  onError: (error: string) => void;
}

const LicenseForm: React.FC<LicenseFormProps> = ({ onLicenseValidated, onError }) => {
  const [licenseKey, setLicenseKey] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [validationError, setValidationError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!licenseKey.trim()) {
      setValidationError('Please enter a license key');
      return;
    }

    setIsValidating(true);
    setValidationError('');

    try {
      const response = await ApiService.validateLicense(licenseKey.trim());
      
      if (response.valid) {
        onLicenseValidated(response.license_info);
      } else {
        setValidationError(response.message || 'Invalid license key');
      }
    } catch (error) {
      setValidationError(`License validation failed: ${error}`);
      onError(`License validation failed: ${error}`);
    } finally {
      setIsValidating(false);
    }
  };

  return (
    <Box maxWidth={600} mx="auto">
      <Box textAlign="center" mb={4}>
        <VpnKey sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
        <Typography variant="h4" gutterBottom>
          License Activation
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Enter your license key to activate Marketplace Magic
        </Typography>
      </Box>

      <form onSubmit={handleSubmit}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="License Key"
              value={licenseKey}
              onChange={(e) => setLicenseKey(e.target.value)}
              placeholder="XXXX-XXXX-XXXX-XXXX"
              disabled={isValidating}
              error={!!validationError}
              helperText={validationError || 'Enter your license key in the format: XXXX-XXXX-XXXX-XXXX'}
              InputProps={{
                style: { fontFamily: 'monospace' }
              }}
            />
          </Grid>

          <Grid item xs={12}>
            <Button
              type="submit"
              variant="contained"
              size="large"
              fullWidth
              disabled={isValidating || !licenseKey.trim()}
              startIcon={isValidating ? <CircularProgress size={20} /> : <Check />}
            >
              {isValidating ? 'Validating...' : 'Validate License'}
            </Button>
          </Grid>
        </Grid>
      </form>

      <Divider sx={{ my: 4 }} />

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Need a License?
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Purchase a license to unlock the full potential of Marketplace Magic automation.
              </Typography>
              <Button
                variant="outlined"
                size="small"
                href="https://your-website.com/purchase"
                target="_blank"
              >
                Purchase License
              </Button>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Test Mode
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Use the test license key for evaluation purposes.
              </Typography>
              <Button
                variant="text"
                size="small"
                onClick={() => setLicenseKey('TEST-1234-5678-9ABC')}
                disabled={isValidating}
              >
                Use Test Key
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Box mt={4}>
        <Alert severity="info">
          <Typography variant="body2">
            <strong>What happens next:</strong>
          </Typography>
          <Typography variant="body2" component="div">
            <ol style={{ margin: 0, paddingLeft: '20px' }}>
              <li>License validation (online check)</li>
              <li>API key configuration</li>
              <li>Automation settings</li>
              <li>Ready to use!</li>
            </ol>
          </Typography>
        </Alert>
      </Box>
    </Box>
  );
};

export default LicenseForm;