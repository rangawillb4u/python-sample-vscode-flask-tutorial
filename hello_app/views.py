from datetime import datetime
from flask import Flask, render_template
from . import app
import base64
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime

import boto3
import botocore
import psycopg2
import requests
from psycopg2._json import Json

from flask import Flask, jsonify, request, make_response, Response, send_file
from flask_cors import CORS
from requests.auth import HTTPBasicAuth

from pyfcm import FCMNotification
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

BASE_FOLDER_PATH = os.path.abspath(__file__ + "/../")

app = Flask(__name__)
app.config["DEBUG"] = True
app.config["JSON_SORT_KEYS"] = False
app

cred = credentials.Certificate(os.path.abspath(BASE_FOLDER_PATH + '/firebase_key.json'))
firebase_admin.initialize_app(cred)

push_service = FCMNotification(
    api_key="AAAAnEhcLJI:APA91bGTpCACkSe4f-dH2pP7hTG4qf8iz8crt-FFsXwTurBCwwafdJ4WcgsDtvkufLQNsukCcgXuXyH0pPY0p8t9siWZ_zlVhtEEIRQLtydpp774t2CcWbQWfwiEFQZY_ujLDN_j9XV9")

import logging


@app.route('/', methods=['GET'])
def home():
    return "Welcome to Deltas V2.0"


@app.route('/get_today_status', methods=['GET'])
def get_today_status():
    response = {
        "result": "Today's execution result is. 95 tests passed and 5 tests failed. It was a excellent run."
    }
    return make_response(jsonify(response), 200)

@app.route('/get_db_execution_logs', methods=['PUT'])
def get_db_execution_logs():
    table_filter = request.json
    print(table_filter)
    columns = []
    rows = []
    editable_columns = ["status", "fail_type", "fail_description", "jira_reference", "comments"]
    width_config = {
        "sno": {"width": 50},
        "test_pack": {"width": 250},
        "test_id": {"width": 450},
        "test_name": {"width": 450},
        "iteration_id": {"width": 100},
        "step_id": {"width": 70},
        "status": {"width": 95},
        "fail_type": {"width": 170},
        "fail_description": {"width": 500},
        "test_triaged_status": {"width": 120},
        "time_stamp": {"width": 250},
        "duration": {"width": 80},
        "comments": {"width": 500}
                    }
    response = {"columns": columns,
                "rows": rows,
                "originalRows": rows,
                "triagedRows": [],
                "selectedIndexes": [],
                "filters": {},
                "sortColumn": "null",
                "sortDirection": "null",
                "emptyColumns": [],
                "reorderedColumns": []
                }
    try:
        conn = get_results_db_conn()
        # if conn.is_connected():
        c = conn.cursor()

        filter_query = ''
        filter_date_query = ''
        filter_exec_id_query = ''
        from_time = ' 00:00:00'
        to_time = ' 23:59:59'
        for key in table_filter.keys():
            if 'DATE' in key.upper():
                if not (table_filter[key] == '' or table_filter[key] == None):
                    from_date = table_filter[key][0].split('T')[0]
                    from_date = datetime.strptime(from_date, '%Y-%m-%d').strftime('%d-%m-%Y')
                    if not table_filter[key][1] is None:
                        to_date = table_filter[key][1].split('T')[0]
                        to_date = datetime.strptime(to_date, '%Y-%m-%d').strftime('%d-%m-%Y')
                    else: to_date = from_date
                    filter_date_query = filter_date_query + "time_stamp between '" + from_date + from_time + "' and '" + to_date + to_time + "'"
                else:
                    str_format = "%d-%m-%Y"
                    today_date = datetime.today().strftime(str_format)
                    filter_date_query = filter_date_query + "time_stamp between '" + today_date + from_time + "' and '" + today_date + to_time + "'"
            if 'EXEC' in key.upper():
                if not 'ALL' in table_filter[key]:
                    if len(table_filter[key]) == 1: table_filter[key].append(table_filter[key][0])
                    exec_ids = str(tuple(table_filter[key]))
                    filter_exec_id_query = " execution_id in " + exec_ids
        if not filter_date_query == '':
            if not filter_exec_id_query == '': filter_query = filter_date_query + ' and ' + filter_exec_id_query
            else: filter_query = filter_date_query
        if len(table_filter.keys()) > 0:
            c.execute("SELECT * FROM execution_logs WHERE " + filter_query + " ORDER BY sno DESC LIMIT 2000 ;")
        else:
            c.execute("SELECT * FROM execution_logs ORDER BY sno DESC LIMIT 2000;")  #" OFFSET 100;"

        column_headers = c.description
        record_set = c.fetchall()
        for column_header in column_headers:
            column_header = column_header.name
            width = 150
            if column_header in width_config.keys(): width = width_config[column_header]["width"]
            editable = False
            if column_header in editable_columns: editable = True
            columns.append({
                "key": column_header,
                "name": column_header,
                "field": column_header,
                "header": column_header,
                "editable": editable,
                "sortable": "true",
                "filterable": "true",
                "resizable": "true",
                "draggable": "true",
                "width": str(width) + "px",
            })
        for rowData in record_set:
            row = {}
            for cntr, data in enumerate(rowData):
                row[column_headers[cntr].name] = data
            rows.append(row)

        #Collecting the execution ids
        executionIDs = ["ALL"]
        if len(table_filter.keys()) > 0:
            c.execute("SELECT DISTINCT execution_id FROM execution_logs WHERE " + filter_query + ";")
        else:
            c.execute("SELECT DISTINCT execution_id FROM execution_logs;")

        record_set = c.fetchall()
        for rowData in record_set:
            for _, data in enumerate(rowData):
                executionIDs.append(data)

        response = {"columns": columns,
                    "rows": rows,
                    "originalRows": rows,
                    "triagedRows": [],
                    "selectedIndexes": [],
                    "filters": {},
                    "sortColumn": "null",
                    "sortDirection": "null",
                    "emptyColumns": [],
                    "reorderedColumns": [],
                    "executionIDs": executionIDs
                    }
    except Exception as e:
        print(e)
        return make_response(jsonify(response), 555) #{"errorMessage": str(e)}
    finally:
        conn.commit()
        conn.close()
    return make_response(jsonify(response), 200)

@app.route('/get_db_triage_data', methods=['GET'])
def get_db_triage_data():
    columns = []
    rows = []
    editable_columns = ["status", "fail_type", "fail_description", "dev_triaged_status", "triage_workflow_status", "jira_reference", "comments", "assignee"]
    width_config = {
        "sno": {"width": 50},
        "test_pack": {"width": 250},
        "test_id": {"width": 450},
        "test_name": {"width": 450},
        "iteration_id": {"width": 100},
        "step_id": {"width": 70},
        "status": {"width": 85},
        "fail_description": {"width": 500},
        "dev_triaged_status": {"width": 150},
        "triage_workflow_status": {"width": 180},
        "last_updated": {"width": 160},
        "time_stamp": {"width": 250},
        "assignee": {"width": 250},
        "duration": {"width": 80},
        "comments": {"width": 500}
                    }
    response = {"columns": columns,
                "rows": rows,
                "originalRows": rows,
                "triagedRows": [],
                "selectedIndexes": [],
                "filters": {},
                "sortColumn": "null",
                "sortDirection": "null",
                "emptyColumns": [],
                "reorderedColumns": []
                }
    try:
        conn = get_results_db_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM Triage ORDER BY sno DESC LIMIT 2000;"
              )
        column_headers = c.description
        record_set = c.fetchall()
        for column_header in column_headers:
            column_header = column_header.name
            width = 150
            if column_header in width_config.keys(): width = width_config[column_header]["width"]
            editable = False
            if column_header in editable_columns: editable = True
            columns.append({
                "key": column_header,
                "name": column_header,
                "field": column_header,
                "header": column_header,
                "editable": editable,
                "sortable": "true",
                "filterable": "true",
                "resizable": "true",
                "draggable": "true",
                "width": str(width)+ "px",
            })
        for rowData in record_set:
            row = {}
            for cntr, data in enumerate(rowData):
                row[column_headers[cntr].name] = data
            rows.append(row)

        response = {"columns": columns,
                    "rows": rows,
                    "originalRows": rows,
                    "triagedRows": [],
                    "selectedIndexes": [],
                    "filters": {},
                    "sortColumn": "null",
                    "sortDirection": "null",
                    "emptyColumns": [],
                    "reorderedColumns": []
                    }
    except Exception as e:
        return make_response(jsonify(response), 555) #{"errorMessage": str(e)}
    finally:
        conn.commit()
        conn.close()
    return make_response(jsonify(response), 200)

@app.route('/update_db_triage_execution_logs', methods=['PUT'])
def update_db_triage_execution_logs():
    selectedRows = request.get_json()
    try:
        conn = get_results_db_conn()

        for row in selectedRows:
            current_time_stamp = datetime.today().strftime("%d-%m-%Y %H:%M:%S")
            c = conn.cursor()
            c.execute("UPDATE execution_logs "
                        "SET "
                        "status = '" + row["status"] + "',"
                        "fail_type = '" + row["fail_type"] + "',"
                        "fail_description = '" + row["fail_description"] + "',"
                        "test_triaged_status = 'YES',"
                        "jira_reference = '" + row["jira_reference"] + "',"
                        "comments = '" + row["comments"] + "' "
                        " WHERE "
                        "sno = '" + str(row["sno"]) + "' AND "
                        "test_id = '" + row["test_id"] + "'"
                        ";")

            c.execute("SELECT fail_type, fail_description, jira_reference, comments FROM triage WHERE " +
                      "test_id ='" + row['test_id'] + "' AND " +
                      "iteration_id ='" + row['iteration_id'] + "' AND " +
                      "step_id ='" + str(row['step_id']) + "';"
                      )
            rs = c.fetchall()
            if len(rs) > 0:
                c.execute("UPDATE triage "
                        "SET "
                        "fail_type = '" + row["fail_type"] + "',"
                        "fail_description = '" + row["fail_description"] + "',"
                        "test_pack = '" + row["test_pack"] + "',"
                        "dev_triaged_status = 'NO',"
                        "triage_workflow_status = 'NEW',"
                        "last_updated = '" + current_time_stamp + "',"
                        "jira_reference = '" + row["jira_reference"] + "',"
                        "comments = '" + row["comments"] + "',"
                        "results = %s"  
                      " WHERE "
                      "test_id ='" + row['test_id'] + "' AND " +
                      "iteration_id ='" + row['iteration_id'] + "' AND " +
                      "step_id ='" + str(row['step_id']) + "'",
                      [Json(row['results'])])
            else:
                c.execute(
                    "INSERT INTO triage (test_pack, test_id, test_name, iteration_id, step_id, fail_type, fail_description, dev_triaged_status, triage_workflow_status, last_updated, jira_reference, comments, results) values ('" +
                    row['test_pack'] + "', '" +
                    row['test_id'] + "', '" +
                    row['test_name'] + "', '" +
                    row['iteration_id'] + "', '" +
                    str(row['step_id']) + "', '" +
                    row['fail_type'] + "', '" +
                    row['fail_description'] + "', '" +
                    "NO', '" +
                    "NEW', '" +
                    current_time_stamp + "', '" +
                    row['jira_reference'] + "', '" +
                    row['comments'] + "', " +
                    "%s" +
                    ")",
                    [Json(row['results'])]
                )
    except Exception as e:
        print(e)
        if conn:
            conn.commit()
            conn.close()
        return make_response(jsonify({"message": "Exception"}), 555) #{"errorMessage": str(e)}
    finally:
        if conn:
            try:
                conn.commit()
                conn.close()
            except: pass
    return make_response(jsonify({"message": "Success"}), 200)


# Updating the triage table
@app.route('/update_db_triage', methods=['PUT'])
def update_db_triage():
    selectedRows = request.get_json()
    try:
        conn = get_results_db_conn()
        print(selectedRows)
        for row in selectedRows:
            current_time_stamp = datetime.today().strftime("%d-%m-%Y %H:%M:%S")
            c = conn.cursor()
            c.execute("UPDATE triage "
                    "SET "
                    "fail_type = '" + row["fail_type"] + "',"
                    "fail_description = '" + row["fail_description"] + "',"
                    "dev_triaged_status = 'YES',"
                    "triage_workflow_status = '" + row['triage_workflow_status'] + "',"
                    "last_updated = '" + current_time_stamp + "',"
                    "jira_reference = '" + row["jira_reference"] + "',"
                    "assignee = '" + str(row["assignee"]) + "',"
                    "comments = '" + str(row["comments"]) + "'"  
                  " WHERE "
                    "sno = '" + str(row["sno"]) + "' AND "
                    "test_id = '" + row["test_id"] + "'"
                    ";")

    except:
        print('Exception in update_db_triage \n {0}'.format(
            traceback.format_exc().replace('File', '$~File')))
        if conn:
            conn.commit()
            conn.close()
        return make_response(jsonify({"message": "Exception"}), 555) #{"errorMessage": str(e)}
    finally:
        if conn:
            try:
                conn.commit()
                conn.close()
            except: pass
    return make_response(jsonify({"message": "Success"}), 200)


#PostGress DB updates from framework
@app.route('/update_db_execution_log/<result_folder>', methods=['PUT'])
def update_db_execution_log(result_folder):
    raise_new_bug = True
    oDictAllIterationDetails = request.json
    conn = None
    try:

        conn = get_results_db_conn()
        # if conn.is_connected():
        c = conn.cursor()
        for _, iter in oDictAllIterationDetails.items():
            if 'FAIL' in iter['status'].upper():
                c.execute("SELECT fail_type, fail_description, jira_reference, comments, triage_workflow_status FROM triage WHERE " +
                          "test_id ='" + iter['testID'] + "' AND " +
                          "iteration_id ='" + iter['iterationID'] + "' AND " +
                          "step_id ='" + str(iter['stepNo']) + "';"
                          )
                rs = c.fetchall()
                if len(rs) > 0:
                    bugStatus = ''
                    bugID = rs[0][2].strip()
                    print("bugID", bugID)

                    if not bugID == "":
                        bugStatus, _ = __get_bug_status(bugID)
                        print("bugstatus", bugStatus)
                    print(iter['testID'], rs[0][4].upper())
                    if not 'DONE' in bugStatus.upper():
                        if not 'DONE' in rs[0][4].upper():
                            iter['failType'] = rs[0][0]
                            iter['failDescription'] = rs[0][1]
                            iter['triagedStatus'] = "Yes"
                            iter['jiraReference'] = rs[0][2]
                            iter['comments'] = rs[0][3]
                            raise_new_bug = False
                #         else:
                #             raise_new_bug =True
                #     else:
                #         raise_new_bug =True
                #
                # else:
                #     raise_new_bug = True

            if raise_new_bug:
                if 'REGRESSION' in iter['executionPhase'].upper():
                    if 'APP' in iter['failType'].upper():
                        bug_details = {
                            "bugSummary": iter["testName"],
                            "bugDescription": iter["failDescription"],
                            "bugPriority": 'Minor',
                            "results": {"resultFolder": result_folder,
                                        "results": iter['results']}
                        }
                        r = __create_bug(bug_details)
                        iter['jiraReference'] = r.json()["key"]

            c.execute(
                "INSERT INTO execution_logs (test_pack, test_id, test_name, iteration_id, step_id, status, fail_type, fail_description, test_triaged_status, time_stamp, duration, jira_reference, execution_id, execution_phase, execution_host, comments, results) values ('" +
                iter['testPack'] + "', '" +
                iter['testID'] + "', '" +
                iter['testName'] + "', '" +
                iter['iterationID'] + "', '" +
                str(iter['stepNo']) + "', '" +
                iter['status'] + "', '" +
                iter['failType'] + "', '" +
                iter['failDescription'] + "', '" +
                iter['triagedStatus'] + "', '" +
                iter['execTime'] + "', '" +
                iter['durationSec'] + "', '" +
                iter['jiraReference'] + "', '" +
                iter['executionID'] + "', '" +
                iter['executionPhase'] + "', '" +
                iter['executionHost'] + "', '" +
                iter['comments'] + "', " +
                "%s" +
                ")",
                [Json({"resultFolder": result_folder,
                       "results": iter['results']})]
            )

    except Exception as e:
        print(e)
    finally:
        if conn:
            conn.commit()
            conn.close()

    return make_response(jsonify({"response": "Successfully inserted/updated execution logs: " }), 200)


def get_results_db_conn():

    conn = None
    try:

        conn = psycopg2.connect(host='ctf-cs-database.ctmgoewjoos7.eu-west-1.rds.amazonaws.com', dbname="pyax", user="CTFAdmin", password="RXFyJ9mg2gGQCnJP")
    except: pass
    return conn


#S3 bucket APIs
@app.route('/s3_upload_screenshot<key>', methods=['POST'])
def s3_upload_screenshot(key):
    screenshot_file = request.files
    key = key.replace("~", "/")
    print("Key", key)

    s3 = boto3.resource('s3')
    resutls_bucket = s3.Bucket('pyax-screenshot-storage')
    screenshot_file["media"].save("my_server_image.png")
    resutls_bucket.upload_file(Filename="my_server_image.png", Key=key)
    return make_response(jsonify({"key": key}), 200)


# @app.route('/s3_upload_screenshot/<result_folder>', methods=['POST'])
# def s3_upload_screenshot(result_folder):
#     # result_folder = request.json()["result_folder"]
#     screenshot_file = request.files
#     month = datetime.today().strftime("%b")
#     year = datetime.today().strftime("%Y")
#     day = datetime.today().strftime("%d").zfill(2)
#     key = "results/" + month + year + "/" + day + "/" + result_folder + "/" + screenshot_file["media"].filename
#
#
#     s3 = boto3.resource('s3')
#     resutls_bucket = s3.Bucket('pyax-screenshot-storage')
#     screenshot_file["media"].save("my_server_image1.png")
#     resutls_bucket.upload_file(Filename="my_server_image1.png", Key=key)
#     print("Key", key)
#     return make_response(jsonify({"key": key}), 200)



#S3 bucket APIs
# @app.route('/s3_upload_screenshot/<result_folder>', methods=['POST'])
# def s3_upload_screenshot(result_folder):
#     # result_folder = request.json()["result_folder"]
#     screenshot_file = request.files
#     month = datetime.today().strftime("%b")
#     year = datetime.today().strftime("%Y")
#     day = datetime.today().strftime("%d").zfill(2)
#     key = "results/" + month + year + "/" + day + "/" + result_folder + "/" + screenshot_file["media"].filename
#
#
#     s3 = boto3.client('s3')
#     s3.put_object(Bucket='pyax-screenshot-storage', Body=screenshot_file["media"] , Key=key)
#
#     return make_response(jsonify({"key": key}), 200)

@app.route('/get_screenshot_by_key1', methods=['PUT'])
def get_screenshot_by_key1():
    s3 = boto3.resource('s3')
    KEY = request.get_json()["key"]
    print(KEY)
    resutls_bucket = s3.Bucket('pyax-screenshot-storage')
    temp_filepath = os.path.abspath(BASE_FOLDER_PATH + '/my_local_image.png')
    print('temp', temp_filepath)
    import botocore
    try:
        resutls_bucket.download_file(KEY, temp_filepath)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            print("The object does not exist.")
        else:
            print("errorr is raised")
            raise

    return send_file(temp_filepath, mimetype='image/gif', attachment_filename='my_local_image.png')

@app.route('/get_screenshot_by_key', methods=['PUT'])
def get_screenshot_by_key():
    s3 = boto3.client('s3')
    KEY = request.get_json()["key"]
    try:
        file = s3.get_object(Bucket='pyax-screenshot-storage', Key=KEY)
        return Response(
            file['Body'].read(),
            mimetype='text/plain',
            headers={"Content-Disposition": "attachment;filename=my_local_image.png"}
        )
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            print("The object does not exist.")
        else:
            print("errorr is raised")
            raise



def get_execution_results():
    table_filter = {'dateRange': ['2019-01-22T00:00:00.000Z', '2019-01-22T00:00:00.000Z']}#request.json
    print(table_filter)
    rows = []
    try:
        conn = get_results_db_conn()
        # if conn.is_connected():
        c = conn.cursor()

        filter_query = ''
        from_time = ' 00:00:00'
        to_time = ' 23:59:59'
        for key in table_filter.keys():
            if 'DATE' in key.upper():
                if not (table_filter[key] == '' or table_filter[key] == None):
                    from_date = table_filter[key][0].split('T')[0]
                    from_date = datetime.strptime(from_date, '%Y-%m-%d').strftime('%d-%m-%Y')
                    if not table_filter[key][1] is None:
                        to_date = table_filter[key][1].split('T')[0]
                        to_date = datetime.strptime(to_date, '%Y-%m-%d').strftime('%d-%m-%Y')
                    else: to_date = from_date
                    filter_query = filter_query + "time_stamp between '" + from_date + from_time + "' and '" + to_date + to_time + "'"
                else:
                    str_format = "%d-%m-%Y"
                    today_date = datetime.today().strftime(str_format)
                    filter_query = filter_query + "time_stamp between '" + today_date + from_time + "' and '" + today_date + to_time + "'"
        if len(table_filter.keys()) > 0:
            c.execute("SELECT * FROM execution_logs WHERE " + filter_query + " ORDER BY sno DESC LIMIT 2000 ;")
        else:
            c.execute("SELECT * FROM execution_logs ORDER BY sno DESC LIMIT 2000;")  #" OFFSET 100;"

        column_headers = c.description
        record_set = c.fetchall()
        for rowData in record_set:
            row = {}
            for cntr, data in enumerate(rowData):
                row[column_headers[cntr].name] = data
            rows.append(row)

        test_report = {}

        for row in rows:
            test_pack = row["test_pack"]
            if test_pack not in test_report.keys():
                # noinspection PyTypeChecker
                test_report[test_pack] = {
                    'Total Implemented': 0,
                    'Passed': 0,
                    'Failed': 0,
                    'UnTriaged': 0,
                    'Blocked': 0,
                    'Environment Issue': 0,
                    'Test / Test Data Issue': 0,
                    'Application Issue': 0,
                }
            if 'PASS' in row["status"].upper(): test_report[test_pack]["Passed"] += 1
            else: test_report[test_pack]['Failed'] += 1
            if 'NO' in row["test_triaged_status"].upper(): test_report[test_pack]['UnTriaged'] += 1
            if 'ENVIRONMENT' in row["fail_type"].upper(): test_report[test_pack]['Environment Issue'] += 1
            if 'TEST' in row["fail_type"].upper(): test_report[test_pack]['Test / Test Data Issue'] += 1
            if 'APPLICATION' in row["fail_type"].upper(): test_report[test_pack]['Application Issue'] += 1
        print(test_report)
    except Exception as e:
        print(e)
        return make_response(jsonify({}), 555) #{"errorMessage": str(e)}
    finally:
        conn.commit()
        conn.close()
    # return make_response(jsonify({}), 200)

@app.route('/create_bug_in_jira', methods=['PUT'])
def create_bug_in_jira():
    bug = request.json
    r = __create_bug(bug)
    # fileName = 'geckodriver.log'
    # cmd = 'curl -D- -u ' + credentials['username'] + ':' + credentials['password'] + ' -X POST -H "X-Atlassian-Token: nocheck" -F "file=@' + \
    #       fileName + '"  https://jira.customappsteam.co.uk/rest/api/2/issue/' + r.json()['key'] + '/attachments'
    # p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    # print(p)

    return make_response(jsonify({"responseJson": r.json(), "statusCode":r.status_code}), 200)


def __create_bug(bug):
    bug_details = {
        "fields": {
            "project": {
                "key": "TPI"
            },
            "summary": bug['bugSummary'],
            "issuetype": {
                "name": "Bug"
            },
            "assignee": {
                "name": "asingh37"
            },
            "priority": {
                "name": bug['bugPriority']
            },
            "labels": [
                "Testing"
            ],
            "description": bug['bugDescription']
        }
    }
    stepsToReplicate = ""
    results = bug['results']
    if 'results' in bug['results'].keys():
        results = results['results']
        businessKeywordList = results['businessKeywordList']
        stepsToReplicate = '\n\nSteps to replicate: \n'
        intCntr = 1
        for busKeyword in businessKeywordList:
            stepsToReplicate = stepsToReplicate + str(intCntr) + '. ' + busKeyword['businessKeyword'] + '\n'
            intCntr += 1
    bug_details['fields']['description'] = bug['bugDescription'] + stepsToReplicate

    print(bug_details)
    headers = {
        "Content-Type": "application/json",
    }
    credentials = {'username': 'rveluswamy', 'password': 'Yuvaraj_12'}
    api_url = "https://jira.customappsteam.co.uk/rest/api/2/issue"
    r = requests.post(api_url, headers=headers, data=json.dumps(bug_details),
                      auth=HTTPBasicAuth(credentials['username'], credentials['password']))
    print(r.json())

    return r


@app.route('/create_bug_in_jira_new', methods=['GET'])
def create_bug_in_jira_new():
    # bug = request.json
    bug_details = {
        "fields": {
            "project": {
                "key": "TPI"
            },
            "summary": 'bugSummary',
            "issuetype": {
                "name": "Bug"
            },
            "assignee": {
                "name": "asingh37"
            },
            "priority": {
                "name": 'Minor'
            },
            "labels": [
                "Testing"
            ],
            "description": 'bugDescription'
        }
    }
    # results = bug['results']['results']
    # businessKeywordList = results['businessKeywordList']
    # stepsToReplicate = '\n\nSteps to replicate: \n'
    # intCntr = 1
    # for busKeyword in businessKeywordList:
    #     stepsToReplicate = stepsToReplicate + str(intCntr) + '. ' + busKeyword['businessKeyword'] + '\n'
    #     intCntr += 1
    # bug_details['fields']['description'] = bug_details['fields']['description'] + stepsToReplicate

    print(bug_details)
    headers = {
        "Content-Type": "application/json",
    }
    credentials = {'username': 'rveluswamy', 'password': 'Yuvaraj_12'}
    api_url = "https://jira.customappsteam.co.uk/rest/api/2/issue"
    r = requests.post(api_url, headers=headers, data=json.dumps(bug_details),
                      auth=HTTPBasicAuth(credentials['username'], credentials['password']))
    print(r.json())
    # fileName = 'geckodriver.log'
    # cmd = 'curl -D- -u ' + credentials['username'] + ':' + credentials['password'] + ' -X POST -H "X-Atlassian-Token: nocheck" -F "file=@' + \
    #       fileName + '"  https://jira.customappsteam.co.uk/rest/api/2/issue/' + r.json()['key'] + '/attachments'
    # p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    # print(p)

    return make_response(jsonify({"responseJson": r.json(), "statusCode":r.status_code}), 200)

@app.route('/get_bug_status/<bugID>', methods=['GET'])
def get_bug_status(bugID):
    status, status_code = __get_bug_status(bugID)
    return make_response(jsonify({"status": status, "statusCode": status_code}), 200)

@app.route('/trigger_regression_build', methods=['GET'])
def trigger_regression_build():
    session = boto3.session.Session()
    kms = session.client('kms')

    execution_id = "alexaTrigger"
    meta = kms.decrypt(CiphertextBlob=base64.b64decode(
        'AQICAHh7svBbqtLhc6tlEkVHZ+FWrMebkfcjM56Nf7fmTcka4QEBZmAuHqHATFZdnsZv9lb/AAAAgDB+BgkqhkiG9w0BBwagcTBvAgEAMGoGCSqGSIb3DQEHATAeBglghkgBZQMEAS4wEQQML3+iQ5jgmGhQKCXzAgEQgD0CgY2fnJzBtvepgpkIMyCRwjafadXFVCac+9Kc2QaEAoXljlaTZeTgZWx7qMKATcEPMZoawqMkg1wjtA+D'))
    jenkins_job_url = "https://ctf:" + meta[
        u'Plaintext'].decode() + "@jenkins.cloud-ops.co.uk/job/Infrastructure%20Tax/job/CTF/job/docker/job/sit_test_pipeline/job/master/buildWithParameters?BRANCH_NAME=" + execution_id
    subprocess.call(['curl', '-X', 'POST', jenkins_job_url])

    return make_response(jsonify({"status": "The SIT and regression CT pipeline is triggered successfully"}), 200) # , "output": output, "err": err

def __get_bug_status(bugID):
    headers = {
        "Content-Type": "application/json",
    }
    credentials = {'username': 'rveluswamy', 'password': 'Yuvaraj_12'}
    api_url = "https://jira.customappsteam.co.uk/rest/api/2/search?jql=key=" + bugID + "&fields=id,key,status"
    r = requests.get(api_url, headers=headers,
                     auth=HTTPBasicAuth(credentials['username'], credentials['password']))
    print(r.json())
    status = r.json()['issues'][0]['fields']['status']['statusCategory']['key']
    return status, r.status_code



def __get_subtasks(bugID):
    headers = {
        "Content-Type": "application/json",
    }
    credentials = {'username': 'rveluswamy', 'password': 'Yuvaraj_12'}
    api_url = "https://jira.customappsteam.co.uk/rest/api/2/search?jql=key=" + bugID + "&fields=id,key,status,subtasks"
    r = requests.get(api_url, headers=headers,
                     auth=HTTPBasicAuth(credentials['username'], credentials['password']))
    subtasks = r.json()['issues'][0]['fields']['subtasks']

    st_list = []
    for subtask in subtasks:
        st_details = {
            "summary": subtask['fields']['summary'],
            "status": subtask['fields']['status']['statusCategory']['key'],
            "key": subtask['key']
        }
        st_list.append(st_details)
    return st_list


def __update_issue_status_done(issue_id):
    headers = {
        "Content-Type": "application/json",
    }
    payload = {"transition": {"id": "41"}}
    credentials = {'username': 'rveluswamy', 'password': 'Yuvaraj_12'}
    api_url = "https://jira.customappsteam.co.uk/rest/api/2/issue/" + issue_id + "/transitions"
    print(api_url)
    r = requests.post(api_url, headers=headers,
                      data=json.dumps(payload),
                     auth=HTTPBasicAuth(credentials['username'], credentials['password']))


def __add_comments_issue(issue_id, comments):
    headers = {
        "Content-Type": "application/json",
    }
    payload = {"body": comments}
    credentials = {'username': 'rveluswamy', 'password': 'Yuvaraj_12'}
    api_url = "https://jira.customappsteam.co.uk/rest/api/2/issue/" + issue_id + "/comment"
    print(api_url)
    r = requests.post(api_url, headers=headers,
                      data=json.dumps(payload),
                     auth=HTTPBasicAuth(credentials['username'], credentials['password']))


def __create_subtask_system_test(issue_id):
    headers = {
        "Content-Type": "application/json",
    }
    payload = {
    "fields":
    {
        "project":
        {
            "key": "TPI"
        },
        "parent":
        {
            "key": issue_id
        },
        "summary": "System Test",
        "description": "System Test",
        "issuetype":
        {
            "id": "5"
        }
    }
}
    credentials = {'username': 'rveluswamy', 'password': 'Yuvaraj_12'}
    api_url = "https://jira.customappsteam.co.uk/rest/api/2/issue/"
    print(api_url)
    r = requests.post(api_url, headers=headers,
                      data=json.dumps(payload),
                     auth=HTTPBasicAuth(credentials['username'], credentials['password']))
    return r.json()["key"]




@app.route('/update_system_test_subtask/<issue_id>', methods=['PUT'])
def update_system_test_subtask(issue_id):
    try:
        test_details = request.json
        print(test_details)
        test_phase = 'System'
        create_subtask = True
        st_key = ''

        test_cntr = 1
        comment_test_details_header = "||Sno||Test Name||Status||\r\n"
        comment_test_details_rows = []
        for test_detail in test_details["testDetails"]:
            comment_test_details_row = '|' + str(test_cntr) + '|' + test_detail['testName'] + '|' + test_detail['status']
            comment_test_details_rows.append(comment_test_details_row)
            test_cntr += 1
        comment_test_details_content = "\r\n".join(comment_test_details_rows)

        comment_summary = "||PASS|" + str(test_details["summary"]["Pass"]) + "\r\n||FAIL|" + str(
            test_details["summary"]["Fail"])

        for subtask in __get_subtasks(issue_id):
            if 'TEST' in subtask['summary'].upper():
                if test_phase.upper() in subtask['summary'].upper():
                    st_key = subtask['key']
                    create_subtask = False
        if create_subtask:
            st_key = __create_subtask_system_test(issue_id)

        __update_issue_status_done(st_key)
        full_comment = "Test execution report.\n\n" + comment_test_details_header + comment_test_details_content \
                       + "\n\n" + comment_summary

        full_comment = full_comment.replace("PASS", "{color:#57d9a3}Pass{color}")
        full_comment = full_comment.replace("FAIL", "{color:#de350b}Fail{color}")
        __add_comments_issue(st_key, full_comment)
    except Exception as e:
        print(e)

    return make_response(jsonify({"responseJson": "Sub task added successfully with the execution report added"
                                                  "to the comments."}), 200)

@app.route('/notify_regression_results', methods=['PUT'])
def notify_regression_results():
    message = request.json

    db = firestore.client()
    users_coll_ref = db.collection(u'users')
    docs = users_coll_ref.get()
    registration_ids = [x.to_dict()["fcmToken"] for x in docs]

    message_title = message["title"]
    message_body = message["body"]
    data = message["data"]
    result = push_service.notify_multiple_devices(registration_ids=registration_ids,
                                                  message_title=message_title,
                                                  message_body=message_body,
                                                  data_message=data,
                                                  sound="default")

    return make_response(jsonify({"response": result}), 200)

#@app.route("/")
#def home():
#    return render_template("home.html")

@app.route("/about/")
def about():
    return render_template("about.html")

@app.route("/contact/")
def contact():
    return render_template("contact.html")

@app.route("/hello/")
@app.route("/hello/<name>")
def hello_there(name = None):
    return render_template(
        "hello_there.html",
        name=name,
        date=datetime.now()
    )

@app.route("/api/data")
def get_data():
    return app.send_static_file("data.json")
