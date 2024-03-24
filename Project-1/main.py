# Imports
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)


import flask
import logging
import os
import tfmodel
from google.cloud import bigquery
from google.cloud import storage

# Set up logging
logging.basicConfig(level=logging.INFO,
                     format='%(asctime)s - %(levelname)s - %(message)s',
                     datefmt='%Y-%m-%d %H:%M:%S')

PROJECT = os.environ.get('GOOGLE_CLOUD_PROJECT') 
logging.info('Google Cloud project is {}'.format(PROJECT))

# Initialisation
logging.info('Initialising app')
app = flask.Flask(__name__)

logging.info('Initialising BigQuery client')
BQ_CLIENT = bigquery.Client()

BUCKET_NAME = PROJECT + '.appspot.com'
logging.info('Initialising access to storage bucket {}'.format(BUCKET_NAME))
APP_BUCKET = storage.Client().bucket(BUCKET_NAME)

logging.info('Initialising TensorFlow classifier')
TF_CLASSIFIER = tfmodel.Model(
    app.root_path + "/static/tflite/model.tflite",
    app.root_path + "/static/tflite/dict.txt"
)
logging.info('Initialisation complete')

# End-point implementation
@app.route('/')
def index():
    return flask.render_template('index.html')

@app.route('/classes')
def classes():
    results = BQ_CLIENT.query(
    '''
        Select Description, COUNT(*) AS NumImages
        FROM `bdcc24project.openimages.image_labels`
        JOIN `bdcc24project.openimages.classes` USING(Label)
        GROUP BY Description
        ORDER BY Description
    ''').result()
    logging.info('classes: results={}'.format(results.total_rows))
    data = dict(results=results)
    return flask.render_template('classes.html', data=data)

@app.route('/relations')
def relations():
    # TODO
    return flask.render_template('not_implemented.html')



@app.route('/image_info')
def image_info():
    image_id = flask.request.args.get('image_id')

    #Fetch classes
    query = '''
        SELECT Description
        FROM `bdcc24project.openimages.image_labels`
        JOIN `bdcc24project.openimages.classes` USING(Label)
        WHERE imageId = @imageId
    '''

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("imageId", "STRING", image_id),
        ]
    )
    
    classes_results = BQ_CLIENT.query(query, job_config=job_config).result()

    #TODO Fetch relations
    ## é preciso ir buscar as labels E de seguida ir buscar os seus nomes reais...
    ## possivelmente tudo na mesma query para eficiencia... 
    ## melhor ainda se desse para juntar com a query de cima
    query = '''
        SELECT Description
        FROM `bdcc24project.openimages.image_labels`
        JOIN `bdcc24project.openimages.classes` USING(Label)
        WHERE imageId = @imageId
    '''

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("imageId", "STRING", image_id),
        ]
    )
    
    classes_results = BQ_CLIENT.query(query, job_config=job_config).result()

    #Fetch image url
    ## e preciso encher o bucket com as imagens, de momento esta vazio
    ## mas em principio e como está em baixo.
    blob = APP_BUCKET.blob(image_id)

    # Generate signed URL with expiry time (in seconds)
    img_url = blob.generate_signed_url(expiration=3600)

    logging.info('classes: results={}'.format(classes_results.total_rows))
    logging.info('img url is: results={}'.format(img_url))
    data = dict(classes_results=classes_results)
    return flask.render_template('image_info.html', image_id=image_id, data=data,img_url=img_url)

@app.route('/image_search')
def image_search():
    description = flask.request.args.get('description', default='')
    image_limit = flask.request.args.get('image_limit', default=10, type=int)
    # TODO
    return flask.render_template('not_implemented.html')

@app.route('/relation_search')
def relation_search():
    class1 = flask.request.args.get('class1', default='%')
    relation = flask.request.args.get('relation', default='%')
    class2 = flask.request.args.get('class2', default='%')
    image_limit = flask.request.args.get('image_limit', default=10, type=int)
    # TODO
    return flask.render_template('not_implemented.html')


@app.route('/image_classify_classes')
def image_classify_classes():
    with open(app.root_path + "/static/tflite/dict.txt", 'r') as f:
        data = dict(results=sorted(list(f)))
        return flask.render_template('image_classify_classes.html', data=data)
 
@app.route('/image_classify', methods=['POST'])
def image_classify():
    files = flask.request.files.getlist('files')
    min_confidence = flask.request.form.get('min_confidence', default=0.25, type=float)
    results = []
    if len(files) > 1 or files[0].filename != '':
        for file in files:
            classifications = TF_CLASSIFIER.classify(file, min_confidence)
            blob = storage.Blob(file.filename, APP_BUCKET)
            blob.upload_from_file(file, blob, content_type=file.mimetype)
            blob.make_public()
            logging.info('image_classify: filename={} blob={} classifications={}'\
                .format(file.filename,blob.name,classifications))
            results.append(dict(bucket=APP_BUCKET,
                                filename=file.filename,
                                classifications=classifications))
    
    data = dict(bucket_name=APP_BUCKET.name, 
                min_confidence=min_confidence, 
                results=results)
    return flask.render_template('image_classify.html', data=data)



if __name__ == '__main__':
    # When invoked as a program.
    logging.info('Starting app')
    app.run(host='127.0.0.1', port=8080, debug=True)
