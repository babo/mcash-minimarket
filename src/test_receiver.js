var http = require('http');
var qs = require('querystring');

var server = http.createServer(function(req, res){
    console.log(req.method + ' ' + req.url);
    console.log(req.headers);
    if (req.method == 'POST') {
        var body = '';
        req.on('data', function (data) {
            body += data;
        });
        req.on('end', function () {
            if (req.headers['content-type'] == 'application/x-www-form-urlencoded'){
                var POST = qs.parse(body);
                console.log(POST);
            }
            else {
                console.log(body);
            }
            
        });
    }

    res.writeHead(200, ['Content-Type', 'application/json']);
    res.write('{"all_rows_removed": 0, "objects": []}');
    res.end('\n');
});

server.listen('9080');
