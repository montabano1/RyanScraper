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
      const response = await fetch(`${getApiBaseUrl()}/properties`);
      if (!response.ok) throw new Error('Failed to fetch properties');
      const data = await response.json();
      setProperties(data);
      setLastUpdated(new Date());
    } catch (err) {
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
      const response = await fetch(`${getApiBaseUrl()}/export`);
      if (!response.ok) throw new Error('Failed to export data');
      const blob = await response.blob();
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

  // Filter properties based on search
  const filteredProperties = properties.filter(property =>
    property.name?.toLowerCase().includes(filter.toLowerCase()) ||
    property.address?.toLowerCase().includes(filter.toLowerCase())
  );

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
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Address</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Source</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Updated</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredProperties.map(property => (
                  <tr key={property.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{property.name}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{property.address}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{property.price}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{property.source}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {format(new Date(property.last_updated), 'MMM d, yyyy HH:mm:ss')}
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
