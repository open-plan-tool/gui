const path = require('path');

module.exports = {
    entry: {
        grid_model_topology: './static_src/js/grid_model_topology.js',
        create_asset_topology: './static_src/js/create_asset_topology.js',
    },
    output: {
        filename: '[name].js',
        path: __dirname + '/static/js',
    },
    module: {
        rules: [
            { test: /\.css$/, use: 'css-loader' },
            {
                test: /\.js$/, // target file type
                exclude: /node_modules/,
                use: ['babel-loader']
            }
        ]
    }
};
