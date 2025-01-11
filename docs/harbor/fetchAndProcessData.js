const fs = require('fs');
const fetch = require('node-fetch');

// Lade die config.json
const config = JSON.parse(fs.readFileSync('config.json', 'utf8'));

// Funktion, um Daten aus der Harbor API zu holen
async function fetchHarborData(apiUrl) {
    try {
        console.log(`Fetching data from: ${apiUrl}`);
        const response = await fetch(apiUrl, {
            method: 'GET',
        });

        if (!response.ok) {
            console.error(`Failed to fetch data from ${apiUrl}:`, response.statusText);
            return [];
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error during fetch:', error);
        return [];
    }
}

// Verarbeite die Daten und speichere sie
async function processConfig() {
    let allRepos = [];

    // Hole die Repository-Daten für jedes Projekt
    for (const apiUrl of config.projects) {
        const repos = await fetchHarborData(apiUrl);
        allRepos = allRepos.concat(repos);
    }

    // Verarbeite die Daten nach Bedarf (z.B. nach Tags filtern oder weitere Anpassungen vornehmen)
    const processedData = {
        date: new Date().toISOString(),
        projects: allRepos.map((repo) => ({
            name: repo.name,
            pull_count: repo.pull_count,
            creation_time: repo.creation_time,
            update_time: repo.update_time
        }))
    };

    // Speichern der verarbeiteten Daten in einer Datei
    fs.writeFileSync('processed-harbor-data.json', JSON.stringify(processedData, null, 2));
    console.log('Data processed and saved to processed-harbor-data.json');
}

processConfig();
