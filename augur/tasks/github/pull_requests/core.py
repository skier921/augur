import time
import logging


from augur.tasks.init.celery_app import celery_app as celery
from augur.application.db.data_parse import *
from augur.tasks.github.util.github_paginator import GithubPaginator, hit_api
from augur.tasks.github.util.github_task_session import GithubTaskSession
from augur.tasks.util.worker_util import wait_child_tasks
from augur.tasks.github.util.util import remove_duplicate_dicts, add_key_value_pair_to_list_of_dicts, get_owner_repo
from augur.application.db.models import PullRequest, Message, PullRequestReview, PullRequestLabel, PullRequestReviewer, PullRequestEvent, PullRequestMeta, PullRequestAssignee, PullRequestReviewMessageRef, PullRequestMessageRef, Contributor, Repo


platform_id = 1


def extract_data_from_pr(pr_data, repo_id, tool_source, tool_version, data_source):

    # adds cntrb_id to reference the contributors table to the 
    # prs, assignees, reviewers, and metadata
    pr_data, contributor_data = process_pull_request_contributors(pr_data, tool_source, tool_version, data_source)

    # add a field called pr_head_or_base to the head and base field of the pr
    # this is done so we can insert them both into the pr metadata table
    # and still determine whether it is a head or base
    pr_data['head'].update(
        {'pr_head_or_base': 'head'}
    )
    pr_data['base'].update(
        {'pr_head_or_base': 'base'}
    )

    # add metadata field to pr
    pr_data.update(
        {"metadata": [pr_data["head"], pr_data["base"]]}
    )

    # create list of pr_dicts to bulk insert later

    pr_needed_data = extract_needed_pr_data(pr_data, repo_id, tool_source,tool_version)

    # get only the needed data for the pull_request_labels table
    pr_labels = extract_needed_pr_label_data(pr_data["labels"],  platform_id, repo_id,
                                                    tool_source, tool_version, data_source)

    # get only the needed data for the pull_request_assignees table
    pr_assignees = extract_needed_pr_assignee_data(pr_data["assignees"], platform_id, repo_id,
                                                            tool_source, tool_version, data_source)

    # get only the needed data for the pull_request_reviewers table
    pr_reviewers = extract_needed_pr_reviewer_data(pr_data["requested_reviewers"], platform_id, repo_id,
                                                            tool_source, tool_version, data_source)

    # get only the needed data for the pull_request_meta table
    pr_metadata = extract_needed_pr_metadata(pr_data["metadata"], platform_id, repo_id,
                                                    tool_source, tool_version, data_source)                                                                      

    return pr_needed_data, pr_labels, pr_assignees, pr_reviewers, pr_metadata, contributor_data


def extract_data_from_pr_list(pull_requests, repo_id, tool_source, tool_version, data_source):

    pr_mapping_data = {}
    pr_dicts = [] 
    pr_numbers = []
    contributors = []
    
    for pr in pull_requests:

        pr_data, labels, assignees, reviewers, metadata, contributor_data = extract_data_from_pr(pr, repo_id, tool_source, tool_version, data_source)

        contributors += contributor_data

        pr_dicts.append(pr_data)
       
        mapping_data_key = pr_data["pr_url"]
        pr_mapping_data[mapping_data_key] = {
                                            "labels": labels,
                                            "assignees": assignees,
                                            "reviewers": reviewers,
                                            "metadata": metadata,
                                            }          
       
         # create a list of pr numbers to pass for the pr reviews task
        pr_numbers.append(pr_data["pr_src_number"]) 

    return pr_dicts, pr_mapping_data, pr_numbers, contributors


def insert_pr_contributors(contributors, session, task_name):

    # remove duplicate contributors before inserting
    contributors = remove_duplicate_dicts(contributors)

    # insert contributors from these prs
    session.logger.info(f"{task_name}: Inserting {len(contributors)} contributors")
    session.insert_data(contributors, Contributor, ["cntrb_login"])


def insert_prs(pr_dicts, session, task_name):

    session.logger.info(f"{task_name}: Inserting prs of length: {len(pr_dicts)}")
    pr_natural_keys = ["pr_url"]
    pr_return_columns = ["pull_request_id", "pr_url"]
    pr_return_data = session.insert_data(pr_dicts, PullRequest, pr_natural_keys, return_columns=pr_return_columns)

    return pr_return_data

def map_other_pr_data_to_pr(pr_return_data, pr_mapping_data, logger):

    pr_label_dicts = []
    pr_assignee_dicts = []
    pr_reviewer_dicts = []
    pr_metadata_dicts = []
    for data in pr_return_data:

        pr_url = data["pr_url"]
        pull_request_id = data["pull_request_id"]

        try:
            other_pr_data = pr_mapping_data[pr_url]
        except KeyError as e:
            logger.info(f"Cold not find other pr data. This should never happen. Error: {e}")


        # add the pull_request_id to the labels, assignees, reviewers, or metadata then add them to a list of dicts that will be inserted soon
        dict_key = "pull_request_id"
        pr_label_dicts += add_key_value_pair_to_list_of_dicts(other_pr_data["labels"], dict_key, pull_request_id)
        pr_assignee_dicts += add_key_value_pair_to_list_of_dicts(other_pr_data["assignees"], dict_key, pull_request_id)
        pr_reviewer_dicts += add_key_value_pair_to_list_of_dicts(other_pr_data["reviewers"], dict_key, pull_request_id)
        pr_metadata_dicts += add_key_value_pair_to_list_of_dicts(other_pr_data["metadata"], dict_key, pull_request_id)

    return pr_label_dicts, pr_assignee_dicts, pr_reviewer_dicts, pr_metadata_dicts 


def insert_pr_labels(labels):

    # we are using pr_src_id and pull_request_id to determine if the label is already in the database.
    pr_label_natural_keys = ['pr_src_id', 'pull_request_id']
    session.insert_data(labels, PullRequestLabel, pr_label_natural_keys)


def insert_pr_assignees(assignees):

    # we are using pr_assignee_src_id and pull_request_id to determine if the label is already in the database.
    pr_assignee_natural_keys = ['pr_assignee_src_id', 'pull_request_id']
    session.insert_data(assignees, PullRequestAssignee, pr_assignee_natural_keys)


def insert_pr_reviewers(reviewers):

    # we are using pr_src_id and pull_request_id to determine if the label is already in the database.
    pr_reviewer_natural_keys = ["pull_request_id", "pr_reviewer_src_id"]
    session.insert_data(reviewers, PullRequestReviewer, pr_reviewer_natural_keys)


def insert_pr_metadata(metadata):

    # inserting pr metadata
    # we are using pull_request_id, pr_head_or_base, and pr_sha to determine if the label is already in the database.
    pr_metadata_natural_keys = ['pull_request_id', 'pr_head_or_base', 'pr_sha']
    session.insert_data(metadata, PullRequestMeta, pr_metadata_natural_keys)




# TODO: Should we insert metadata without user relation?
# NOTE: For contributor related operations: extract_needed_contributor_data takes a piece of github contributor data
# and creates a cntrb_id (primary key for the contributors table) and gets the data needed for the table
def process_pull_request_contributors(pr, tool_source, tool_version, data_source):

    contributors = []

    # get contributor data and set pr cntrb_id
    pr_cntrb = extract_needed_contributor_data(pr["user"], tool_source, tool_version, data_source)
    pr["cntrb_id"] = pr_cntrb["cntrb_id"]

    contributors.append(pr_cntrb)


    if pr["base"]["user"]:

        # get contributor data and set pr metadat cntrb_id
        pr_meta_base_cntrb = extract_needed_contributor_data(pr["base"]["user"], tool_source, tool_version, data_source)
        pr["base"]["cntrb_id"] = pr_meta_base_cntrb["cntrb_id"]

        contributors.append(pr_meta_base_cntrb)

    if pr["head"]["user"]:

        pr_meta_head_cntrb = extract_needed_contributor_data(pr["head"]["user"], tool_source, tool_version, data_source)
        pr["head"]["cntrb_id"] = pr_meta_head_cntrb["cntrb_id"]

        contributors.append(pr_meta_head_cntrb)

    # set cntrb_id for assignees
    for assignee in pr["assignees"]:

        pr_asignee_cntrb = extract_needed_contributor_data(assignee, tool_source, tool_version, data_source)
        assignee["cntrb_id"] = pr_asignee_cntrb["cntrb_id"]

        contributors.append(pr_asignee_cntrb)


    # set cntrb_id for reviewers
    for reviewer in pr["requested_reviewers"]:

        pr_reviwer_cntrb = extract_needed_contributor_data(reviewer, tool_source, tool_version, data_source)
        reviewer["cntrb_id"] = pr_reviwer_cntrb["cntrb_id"]

        contributors.append(pr_reviwer_cntrb)

    return pr, contributors