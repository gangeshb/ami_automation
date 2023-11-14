import os
import json
import subprocess
import boto3

class AMITree:
    # List of files to ignore, which may creep in through git commits
    IGNORE_LIST = set([".DS_Store"])

    # The root directory of the ami inheritance tree
    ROOT_DIR = "ami"

    # The name of the directory which will contain the provisioning scripts
    SCRIPTS_DIR = "provisioners"

    # The separator to use to separate version names from ami names
    VERSION_SEPARATOR = "-"
    # The separator to use to separate ami names
    NODE_SEPARATOR = "_"

    def __init__(self):
        # This will hold the tree representation
        self.tree = {}

    def addNode(self, path: str, nodes: list, files: list = []) -> dict:
        # Remove any ignore list names
        nodes = list(set(nodes) - self.IGNORE_LIST)
        files = list(set(files) - self.IGNORE_LIST)

        # We are going to use path to set up the tree-like structure
        # with slashes representing a level of inheritance
        parts = path.split("/")
        # Start with targetNode being the root of self.tree
        targetNode = self.tree
        # Break path up, and start recursing
        for part in parts:
            if part not in targetNode:
                # If key does not exist, then create a node
                targetNode[part] = {}
            targetNode = targetNode[part]

        # Now, if we are at the last level, and that level is ...
        if part == self.SCRIPTS_DIR:
            # ...the scripts directory then we need to only capture
            # the file names, minus the extension, and that will act as the version numbers
            for file in files:
                version, extension = file.split(".")
                targetNode.append(int(version))
        else:
            # ...any other directory, then we need to create nodes for
            # the subdirectories
            for node in nodes:
                if node == self.SCRIPTS_DIR:
                    targetNode[node] = []
                else:
                    targetNode[node] = {}

    def __prepareAMIList(self, rootKey: str, nodes: dict) -> list:
        
        # Get the list of keys in the node object
        keys = nodes.keys()
        # The list of AMIs to return
        amiList = []
        thisAMI = (rootKey + self.VERSION_SEPARATOR + (str(sorted(nodes[self.SCRIPTS_DIR])[-1]) if self.SCRIPTS_DIR in keys else "")).strip(self.VERSION_SEPARATOR)
        # For each node in nodes ...
        for key in keys:
            # ...if this is not a scripts directory, as there can be no inheritance inside
            # the scripts directory.
            if key != self.SCRIPTS_DIR:
                # ...get the list from any other child nodes in the inheritance tree
                amiList += self.__prepareAMIList(key, nodes[key])
        # Return the AMI for rootKey, and add the current AMI as a suffix to all the child AMIs
        return [thisAMI] + [ami + self.NODE_SEPARATOR + thisAMI for ami in amiList]

    def generateAMIList(self) -> list:
       
        amiList = self.__prepareAMIList(self.ROOT_DIR, self.tree[self.ROOT_DIR])

        # This will hold the final list of AMIs to create.
        result = []
        for ami in amiList:
            # Check if AMI name has fewer than 2 NODE_SEPARATORs, in which case ignore this name
            if ami.count(self.NODE_SEPARATOR) < 2:
                continue

            result.append(ami)

        amiProvisioners = []
        for ami in result:
            nodes = ami.split(self.NODE_SEPARATOR)
            source_ami = nodes[0]
            baseAMI = self.NODE_SEPARATOR.join(nodes[1:])
            nodes.reverse()
            provisionerPath = ""
            if nodes[-1].count(self.VERSION_SEPARATOR) == 0:
                continue
            for node in nodes[:-1]:
                provisionerPath += "%s/" % (node.split(self.VERSION_SEPARATOR)[0])
            provisionerPath += "%s/provisioners/%s.sh" % (nodes[-1].split(self.VERSION_SEPARATOR)[0], nodes[-1].split(self.VERSION_SEPARATOR)[1])
            amiProvisioners.append({
                "name": ami,
                "sourceAMI": baseAMI,
                "provisioner": provisionerPath
            })
        return amiProvisioners

    def get(self):
        return self.tree

class AMIBuilder:
    def __init__(self):
        self.existing_amis = {}

    def fetch_existing_amis(self):
        ami_query_result = subprocess.check_output(["aws", "ec2", "describe-images", "--query", "Images[*].[Name, ImageId]", "--owners", "self"])
        ami_data = eval(ami_query_result.decode("utf-8"))

        for ami_name, existing_ami_id in ami_data:
            self.existing_amis[ami_name] = existing_ami_id
        print(self.existing_amis)

    def build_ami(self, ami_name, source_ami_id, provisioner_script):
        path=os.getcwd()
        full_provisioner_path = os.path.join(os.getcwd(), provisioner_script)
        print("Creating %s from %s with %s" % (ami_name, source_ami_id, full_provisioner_path))
        subprocess.run(["packer", "build", "-var", f"ami_name={ami_name}", "-var", f"source_ami={source_ami_id}", "-var", f"provisioner_script={full_provisioner_path}", "ami_build.pkr.hcl"])

    def ami_compare(self, ami_name, source_ami, provisioner_script):
        existing_ami_id = self.existing_amis.get(ami_name)
        print(existing_ami_id)
        return existing_ami_id is not None

    def process_amis(self, ami_configs):
        for ami_config in ami_configs:
            ami_name = ami_config["name"]
            source_ami = ami_config["sourceAMI"]
            provisioner_script = ami_config["provisioner"]
            # The ami we are about to create should not already be existing
            if ami_name not in self.existing_amis:
                # The source AMI we need should be present
                if source_ami in self.existing_amis:
                    print("Going to create %s from %s" % (ami_name, source_ami))
                    self.build_ami(ami_name, self.existing_amis[source_ami], provisioner_script)
                    self.fetch_existing_amis()
            """
            ami_exists = self.ami_compare(ami_name, source_ami, provisioner_script)
            ec2 = boto3.client('ec2')
            response = ec2.describe_images(Filters=[
            {
                'Name': 'name',
                'Values': [source_ami]
                }
            ])
            images = response['Images']
            # if len(images) == 0:
            #     return None
            # else:
            #     return images[0]['ImageId']

            if ami_exists:
                print(f"{ami_name} with AMI ID {self.existing_amis[ami_name]} already exists")
            else:
                self.build_ami(ami_name, self.existing_amis[source_ami], provisioner_script)
            """
def main():
    # Path of this script
    root = os.path.dirname(__file__) + "/"
    print(subprocess.check_output("pwd"))
    print(subprocess.check_output("ls -al"))

    # The tree object    
    tree = AMITree()
    
    # Get all the files and subdirectories in this directory
    for dirpath, dirs, files in os.walk(os.path.dirname(__file__) + "/ami"):
        tree.addNode(dirpath[len(root):], dirs, files)

    print(json.dumps(tree.get(), sort_keys=True, indent=4))

    ami_manager = AMIBuilder()
    ami_manager.fetch_existing_amis()
    ami_configs = tree.generateAMIList()
    ami_manager.process_amis(ami_configs)

if __name__ == "__main__":
    main()
