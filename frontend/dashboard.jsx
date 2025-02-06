import React, { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { getApiBaseUrl } from './config';

const Dashboard = () => {
  // State management
  const [properties, setProperties] = useState([]);
  const [scrapers, setScrapers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('');
  const [runningScrapers, setRunningScrapers] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Fetch data on component mount
  useEffect(() => {
    fetchProperties();
    fetchScrapers();
  }, []);

  // API calls
  const fetchProperties = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('Fetching properties...');
      const response = await fetch(`${getApiBaseUrl()}/properties`);
      if (!response.ok) throw new Error('Failed to fetch properties');
      const data = await response.json();
      console.log('Received properties:', data);
      setProperties(data);
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Error fetching properties:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchScrapers = async () => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/scrapers`);
      if (!response.ok) throw new Error('Failed to fetch scrapers');
      const data = await response.json();
      setScrapers(data);
    } catch (err) {
      console.error('Error fetching scrapers:', err);
    }
  };

  const runScraper = async (scraperId) => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/scrapers/${scraperId}/run`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Failed to run scraper');
      setRunningScrapers(prev => [...prev, scraperId]);
      // Refresh properties after scraper runs
      setTimeout(fetchProperties, 5000);
    } catch (err) {
      console.error('Error running scraper:', err);
    }
  };

  const exportData = async () => {
    try {
      console.log('Starting export with filtered properties:', filteredProperties);
      // Define column order to match dashboard
      const columnOrder = [
        'Property',
        'Address',
        'Floor/Suite',
        'Space (sq ft)',
        'Price',
        'Source',
        'Listing URL',
        'Last Updated'
      ];

      // Log a sample property to see field names
      if (filteredProperties.length > 0) {
        console.log('Sample property fields:', Object.keys(filteredProperties[0]));
        console.log('Sample property data:', filteredProperties[0]);
      }

      // Format the data to match the dashboard display
      const formattedProperties = filteredProperties.map(p => {
        const formatted = {
          Property: p.property_name || 'N/A',
          Address: p.address || 'N/A',
          'Floor/Suite': p.floor_suite || 'N/A',
          'Space (sq ft)': p.space_available || 'N/A',
          Price: p.price || 'N/A',
          Source: p.source || 'N/A',
          'Listing URL': p.listing_url || 'N/A',
          'Last Updated': p.updated_at ? format(new Date(p.updated_at), 'MMM d, yyyy HH:mm:ss') : 'N/A'
        };
        // Return object with properties in the correct order
        return columnOrder.reduce((obj, key) => ({ ...obj, [key]: formatted[key] }), {});
      });

      console.log('Making export request to:', `${getApiBaseUrl()}/export`);
      const requestData = { properties: formattedProperties };
      console.log('Request data:', requestData);
      
      const response = await fetch(`${getApiBaseUrl()}/export`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
      });
      
      console.log('Export response status:', response.status);
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Export error:', errorText);
        throw new Error(`Failed to export data: ${errorText}`);
      }
      
      const blob = await response.blob();
      console.log('Received blob:', blob);
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'properties.csv';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error exporting data:', err);
    }
  };

  // Filter properties based on search across all relevant fields
  const filteredProperties = properties.filter(property => {
    const searchTerm = filter.toLowerCase();
    return [
      property.property_name,
      property.address,
      property.floor_suite,
      property.space_available,
      property.price,
      property.source,
      property.listing_url
    ].some(field => field?.toString().toLowerCase().includes(searchTerm));
  });

  return (
    <div className="min-h-screen bg-gray-100 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Property Listings Dashboard</h1>
              <p className="text-sm text-gray-500 mt-1">
                {properties.length} properties • Last updated: {lastUpdated ? format(lastUpdated, 'MMM d, yyyy HH:mm:ss') : 'Never'}
              </p>
            </div>
            <div className="flex gap-4">
              <button
                onClick={fetchProperties}
                className={`px-4 py-2 rounded-md text-white ${loading ? 'bg-blue-400' : 'bg-blue-600 hover:bg-blue-700'}`}
                disabled={loading}
              >
                {loading ? 'Refreshing...' : 'Refresh'}
              </button>
              <button
                onClick={exportData}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-md"
              >
                Export CSV
              </button>
            </div>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-8">
            <div className="flex">
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Scrapers grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {scrapers.map(scraper => (
            <div key={scraper.id} className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900">{scraper.name}</h3>
              <p className="text-sm text-gray-500 mt-1">
                Next run: {format(new Date(scraper.next_run), 'MMM d, yyyy HH:mm:ss')}
              </p>
              <button
                onClick={() => runScraper(scraper.id)}
                className={`mt-4 w-full px-4 py-2 rounded-md text-white
                  ${runningScrapers.includes(scraper.id)
                    ? 'bg-gray-400'
                    : 'bg-blue-600 hover:bg-blue-700'
                  }`}
                disabled={runningScrapers.includes(scraper.id)}
              >
                {runningScrapers.includes(scraper.id) ? 'Running...' : 'Run Now'}
              </button>
            </div>
          ))}
        </div>

        {/* Search input */}
        <div className="mb-6">
          <input
            type="text"
            placeholder="Search properties by name or address..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full px-4 py-2 rounded-md border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Properties table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Property</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Address</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Floor/Suite</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Space (sq ft)</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Source</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Listing</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Updated</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredProperties.map(property => (
                  <tr key={property.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{property.property_name || 'N/A'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{property.address}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{property.floor_suite || 'N/A'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{property.space_available || 'N/A'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{property.price}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{property.source}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {property.listing_url ? (
                        <a 
                          href={property.listing_url} 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className="text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          View
                        </a>
                      ) : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {property.updated_at ? format(new Date(property.updated_at), 'MMM d, yyyy HH:mm:ss') : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
