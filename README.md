const AWS = require('aws-sdk');
const s3 = new AWS.S3();

exports.handler = async (event) => {
    const bucket = process.env.S3_BUCKET;
    const key = process.env.VIDEO_KEY;

    try {
        const params = {
            Bucket: bucket,
            Key: key,
            Expires: 300 // URL expires in 5 minutes
        };
        const url = s3.getSignedUrl('getObject', params);

        return {
            statusCode: 200,
            headers: {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            body: JSON.stringify({ videoUrl: url })
        };
    } catch (err) {
        console.error("Error generating pre-signed URL:", err);
        return {
            statusCode: 500,
            body: JSON.stringify({ message: "Failed to retrieve video." })
        };
    }
};
