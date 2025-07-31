const express = require('express');
const axios = require('axios');
const app = express();
const port = 3000;

// Middleware to parse JSON bodies
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Enable CORS to allow frontend to communicate with backend
app.use((req, res, next) => {
    res.header('Access-Control-Allow-Origin', '*');
    res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
    next();
});

// Endpoint to generate label
app.post('/generate-label', async (req, res) => {
    const zpl = req.body.zpl;

    if (!zpl) {
        return res.status(400).json({ error: 'ZPL code is required' });
    }

    try {
        const response = await axios.post(
            'http://api.labelary.com/v1/printers/8dpmm/labels/4x6/0/',
            zpl,
            {
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'image/png'
                },
                responseType: 'arraybuffer' // Handle binary data (PNG)
            }
        );

        // Send the image data back to the client
        res.set('Content-Type', 'image/png');
        res.send(response.data);
    } catch (error) {
        console.error('Error generating label:', error.message);
        res.status(500).json({ error: `Error generating label: ${error.message}` });
    }
});

// Serve the frontend HTML file
app.get('/', (req, res) => {
    res.sendFile(__dirname + '/zebraview.html');
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});