import uuid


def after_job_commit_msg(token: uuid, mode):
    return f"Saved blueprint {str(token)} after {mode}"
