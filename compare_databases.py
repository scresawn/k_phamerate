#!/usr/bin/env python
#Database comparison script
#University of Pittsburgh
#Travis Mavrich
#20170203
#The purpose of this script is to compare the Phamerator, phagesdb, and NCBI databases for inconsistencies and report what needs to be updated.

# Note this script compares and matches data from Genbank data and Phamerator data. As a result, there are many similarly
# named variables. Variables are prefixed to indicate database:
#NCBI =  "ncbi".
#Phamerator = "ph"
#phagesdb = "pdb"


#Built-in libraries
import time, sys, os, getpass, csv, re, shutil
import json, urllib, urllib2

#Third-party libraries
import MySQLdb as mdb




#Define several functions

#Print out statements to both the terminal and to the output file
def write_out(filename,statement):
    print statement
    filename.write(statement)


#Exits MySQL
def mdb_exit(message):
    write_out(report_file,"\nError: " + `sys.exc_info()[0]`+ ":" +  `sys.exc_info()[1]` + "at: " + `sys.exc_info()[2]`)
    write_out(report_file,message)
    write_out(report_file,"\nThe import script did not complete.")
    write_out(report_file,"\nExiting MySQL.")
    cur.execute("ROLLBACK")
    cur.execute("SET autocommit = 1")
    cur.close()
    con.close()
    write_out(report_file,"\nExiting import script.")
    report_file.close()
    sys.exit(1)

#Closes all file handles currently open
def close_all_files(file_list):
    for file_handle in file_list:
        file_handle.close()

#Make sure there is no "_Draft" suffix
def remove_draft_suffix(value):
    # Is the word "_Draft" appended to the end of the name?
    value_truncated = value.lower()
    if value[-6:] == "_draft":
        value_truncated = value[:-6]
    return value_truncated

def parse_strand(value):
    value = value.lower()
    if value == "f" or value == "forward":
        value = "forward"
    elif value == "r" or value == "reverse":
        value = "reverse"
    else:
        value = "NA"
    return value


#Function to split gene description field
def retrieve_description(description):
    description = description.lower().strip()
    return description

#Function to search through a list of elements using a regular expression
def find_name(expression,list_of_items):
    search_tally = 0
    for element in list_of_items:
        search_result = expression.search(element)
        if search_result:
            search_tally += 1
    return search_tally


#Allows user to select specific options
def select_option(message):
    response = 'no'
    response_valid = False
    while response_valid == False:
        response = raw_input(message)
        if (response.lower() == 'yes' or response.lower() == 'y'):
            response  = 'yes'
            response_valid = True
        elif (response.lower() == 'no' or response.lower() == 'n'):
            response = 'no'
            response_valid = True
        else:
            print 'Invalid response.'
    return response






#Define data classes



#Base genome class
class UnannotatedGenome:

    # Initialize all attributes:
    def __init__(self):

        # Non-computed datafields
        self.__phage_name = ''
        self.__host = ''
        self.__sequence = ''
        self.__accession = ''


        # Computed datafields
        self.__search_name = '' # The phage name void of "_Draft" and converted to lowercase
        self.__length = 0
        self.__nucleotide_errors = 0


    # Define all attribute setters:
    def set_phage_name(self,value):
        self.__phage_name = value
        self.__search_name = remove_draft_suffix(self.__phage_name)
    def set_host(self,value):
        self.__host = value
    def set_sequence(self,value):
        self.__sequence = value.upper()
        self.__length = len(self.__sequence)
    def set_accession(self,value):
        if value is None or value.strip() == '':
            self.__accession = ''
        else:
            value = value.strip()
            self.__accession = value.split('.')[0]
    def set_nucleotide_errors(self,dna_alphabet_set):
        nucleotide_set = set(self.__sequence)
        nucleotide_error_set = nucleotide_set - dna_alphabet_set
        self.__nucleotide_errors = len(nucleotide_error_set)



    # Define all attribute getters:
    def get_name(self):
        return self.__name
    def get_host(self):
        return self.__host
    def get_sequence(self):
        return self.__sequence
    def get_length(self):
        return self.__length
    def get_accession(self):
        return self.__accession
    def get_search_name(self):
        return self.__search_name
    def get_nucleotide_errors(self):
        return self.__nucleotide_errors




class AnnotatedGenome(UnannotatedGenome):

    # Initialize all attributes:
    def __init__(self):
        UnannotatedGenome.__init__(self)

        # Non-computed datafields

        # Computed datafields
        self.__cds_features = []
        self.__cds_dict = {}
        self.__cds_features_tally = 0
        self.__cds_features_with_translation_error_tally = 0
        self.__cds_feature_boundary_error_tally = 0
        self.__duplicate_cds_features = False

    # Define all attribute setters:
    def set_cds_features(self,value):
        self.__cds_features = value #Should be a list
        self.__cds_features_tally = len(self.__cds_features)
        #Now create the cds dictionary
        for cds in self.__cds_features:
            if cds.get_start_end_strand_id() not in cds_dict.keys():
                self.__cds_dict[cds.get_start_end_strand_id()] = cds
            else:
                print 'Error: more than one CDS contains identical start, stop, and strand data'
                print 'Phage: %s' %self.__phage_name
                print 'Feature start, stop, strand: %s' %cds.get_start_end_strand_id()
                self.__duplicate_cds_features = True
                raw_input('Press ENTER to continue.')

    def compute_cds_feature_errors(self):
        translation_error_tally = 0
        boundary_error_tally = 0
        for cds_feature in self.__cds_features:
            if cds_feature.get_amino_acid_errors() > 0:
                translation_error_tally += 1
            if cds_feature.get_boundary_error() > 0:
                boundary_error_tally += 1
        self.__cds_features_with_translation_error_tally = translation_error_tally
        self.__cds_feature_boundary_error_tally = boundary_error_tally

    # Define all attribute getters:
    def get_cds_features(self):
        return self.__cds_features
    def get_cds_dict(self):
        return self.__cds_dict
    def get_cds_features_tally(self):
        return self.__cds_features_tally
    def get_cds_features_with_translation_error_tally(self):
        return self.__cds_features_with_translation_error_tally
    def get_cds_feature_boundary_error_tally(self):
        return self.__cds_feature_boundary_error_tally
    def get_duplicate_cds_features(self):
        return self.__duplicate_cds_features





class PhameratorGenome(AnnotatedGenome):

    # Initialize all attributes:
    def __init__(self):
        AnnotatedGenome.__init__(self)
        # Non-computed datafields
        self.__phage_id = ''
        self.__status = '' #Final, Draft, Gbk version of genome data
        self.__cluster_subcluster = '' #Combined cluster_subcluster data.
        self.__ncbi_update_flag = ''

        # Computed datafields
        self.__search_id = '' # The phage ID void of "_Draft" and converted to lowercase


    # Define all attribute setters:
    def set_phage_id(self,value):
        self.__phage_id = value
        self.__search_id = remove_draft_suffix(self.__phage_id)
    def set_status(self,value):
        self.__status = value
    def set_cluster_subcluster(self,value):
        if value is None:
            self.__cluster_subcluster = 'Singleton'
        else:
            self.__cluster_subcluster = value
    def set_ncbi_update_flag(self,value):
        self.__ncbi_update_flag = value


    # Define all attribute getters:
    def get_phage_id(self):
        return self.__phage_id
    def get_cluster_subcluster(self):
        return self.__cluster_subcluster
    def get_status(self):
        return self.__status
    def get_search_id(self):
        return self.__search_id
    def get_ncbi_update_flag(self):
        return self.__ncbi_update_flag



class PhagesdbGenome(UnannotatedGenome):

    # Initialize all attributes:
    def __init__(self):
        UnannotatedGenome.__init__(self)

        # Non-computed datafields
        self.__cluster = ''
        self.__subcluster = ''

        # Computed datafields

    # Define all attribute setters:
    def set_cluster(self,value):
        self.__cluster = value
    def set_subcluster(self,value):
        self.__subcluster = value

    # Define all attribute getters:
    def get_cluster(self):
        return self.__cluster
    def get_subcluster(self):
        return self.__subcluster



class NcbiGenome(AnnotatedGenome):

    # Initialize all attributes:
    def __init__(self):
        AnnotatedGenome.__init_(self)

        #Non-computed data fields
        self.__record_name = ''
        self.__record_id = ''
        self.__record_accession = ''
        self.__record_description = ''
        self.__record_source = ''
        self.__record_organism = ''
        self.__source_feature_organism = ''
        self.__source_feature_host = ''
        self.__source_feature_lab_host = ''


        #Computed data fields
        self.__tally_function_descriptions = 0 #specific to NCBI records
        self.__tally_product_descriptions = 0 #specific to NCBI records
        self.__tally_note_descriptions = 0 #specific to NCBI records
        self.__tally_missing_locus_tags = 0 #specific to NCBI records
        self.__tally_locus_tag_typos = 0 #specific to NCBI records

    #Define setter functions
    def set_record_name(self,value):
        self.__record_name = value
    def set_record_id(self,value):
        self.__record_id = ''
    def set_record_accession(self,value):
        self.__record_accession = value
    def set_record_description(self,value):
        self.__record_description = ''
    def set_record_source(self,value):
        self.__record_source = ''
    def set_record_organism(self,value):
        self.__record_organism = ''
    def set_source_feature_organism(self,value):
        self.__source_feature_organism = ''
    def set_source_feature_host(self,value):
        self.__source_feature_host = ''
    def set_source_feature_lab_host(self,value):
        self.__source_feature_lab_host = ''


    def compute_ncbi_cds_feature_errors(self):
        for cds_feature in self.__cds_features:
            if cds_feature.get_product_description() != '':
                self.__tally_product_descriptions += 1
            if cds_feature.get_function_description() != '':
                self.__tally_function_descriptions += 1
            if cds_feature.get_note_description() != '':
                self.__tally_note_descriptions += 1
            if cds_feature.get_locus_tag() == '':
                self.__tally_missing_locus_tags += 1
            else:
                pattern4 = re.compile(self.__search_name)
                search_result = pattern4.search(cds_feature.get_locus_tag())
                if search_result == None:
                    self.__tally_locus_tag_typos += 1

    #Define getter functions
    def get_record_name(self):
        return self.__record_name
    def get_record_id(self):
        return self.__record_id
    def get_record_accession(self):
        return self.__record_accession
    def get_record_description(self):
        return self.__record_description
    def get_record_source(self):
        return self.__record_source
    def get_record_organism(self):
        return self.__record_organism
    def get_source_feature_organism(self):
        return self.__source_feature_organism
    def get_source_feature_host(self):
        return self.__source_feature_host
    def get_source_feature_lab_host(self):
        return self.__source_feature_lab_host
    def get_tally_function_descriptions(self):
        return self.__tally_function_descriptions
    def get_tally_product_descriptions(self):
        return self.__tally_product_descriptions
    def get_tally_note_descriptions(self):
        return self.__tally_note_descriptions
    def get_tally_missing_locus_tags(self):
        return self.__tally_missing_locus_tags
    def get_tally_locus_tag_typos(self):
        return self.__tally_locus_tag_typos




class CdsFeature:

    # Initialize all attributes:
    def __init__(self):

        # Initialize all non-calculated attributes:

        #Datafields from Phamerator database:
        self.__type_id = '' #Feature type: CDS, GenomeBoundary,or tRNA
        self.__left_boundary = '' #Position of left boundary of feature, 0-indexed
        self.__right_boundary = '' #Position of right boundary of feature, 0-indexed
        self.__strand = '' #'forward', 'reverse', or 'NA'
        self.__translation = ''
        self.__translation_length = ''

        # Computed datafields
        self.__amino_acid_errors = 0
        self.__start_end_strand_id = ''
        self.__boundary_error = 0

    # Define all attribute setters:
    def set_left_boundary(self,value):
        self.__left_boundary = value
    def set_right_boundary(self,value):
        self.__right_boundary = value
    def set_strand(self,value):
        self.__strand = parse_strand(value)
    def set_translation(self,value):
        self.__translation = value.upper()
        self.__translation_length = len(self.__translation)
    def set_type_id(self,value):
        self.__type_id = value
    def set_amino_acid_errors(self,protein_alphabet_set):
        amino_acid_set = set(self.__translation)
        amino_acid_error_set = amino_acid_set - protein_alphabet_set
        self.__amino_acid_errors = len(amino_acid_error_set)
    def set_start_end_strand_id(self):
        #Create a tuple of feature location data.
        #For start and end of feature, it doesn't matter whether the feature is complex with a translational
        #frameshift or not. Retrieving the "start" and "end" attributes return the very beginning and end of
        #the feature, disregarding the inner "join" coordinates.
        self.__start_end_strand_id = (self.__left_boundary,self.__right_boundary,self.__strand)
    def compute_boundary_error(self):
        #Check if start and end coordinates are fuzzy
        if not (self.__left_boundary.isdigit() and self.__right_boundary.isdigit()):
            self.__boundary_error += 1



    # Define all attribute getters:
    def get_left_boundary(self):
        return self.__left_boundary
    def get_right_boundary(self):
        return self.__right_boundary
    def get_type_id(self):
        return self.__type_id
    def get_strand(self):
        return self.__strand
    def get_amino_acid_errors(self):
        return self.__amino_acid_errors
    def get_translation(self):
        return self.__translation
    def get_translation_length(self):
        return self.__translation_length
    def get_start_end_strand_id(self):
        return self.__start_end_strand_id
    def get_boundary_error(self):
        return self.__boundary_error


class PhameratorCdsFeature(CdsFeature):

    # Initialize all attributes:
    def __init__(self):
        CdsFeature.__init__(self)

        # Initialize all non-calculated attributes:

        #Datafields from Phamerator database:
        self.__phage_id = ''
        self.__gene_id = '' #Gene ID comprised of PhageID and Gene name
        self.__gene_name = ''
        self.__notes = ''

        # Computed datafields
        self.__search_id = ''

    # Define all attribute setters:
    def set_phage_id(self,value):
        self.__phage_id = value
        self.__search_id = remove_draft_suffix(self.__phage_id)
    def set_gene_id(self,value):
        self.__gene_id = value
    def set_gene_name(self,name):
        self.__gene_name = name
    def set_notes(self,value):
        self.__notes = value

    # Define all attribute getters:
    def get_gene_id(self):
        return self.__gene_id
    def get_gene_name(self):
        return self.__gene_name
    def get_notes(self):
        return self.__notes
    def get_phage_id(self):
        return self.__phage_id
    def get_search_id(self):
        return self.__search_id



class NcbiCdsFeature(CdsFeature):

    # Initialize all attributes:
    def __init__(self):
        CdsFeature.__init__(self)

        # Initialize all non-calculated attributes:
        self.__locus_tag = '' #Gene ID comprised of PhageID and Gene name
        self.__gene_number = ''
        self.__product_description = ''
        self.__function_description = ''
        self.__note_description = ''
        self.__locus_tag_missing = False


    # Define all attribute setters:
    def set_locus_tag(self,value):
        self.__locus_tag = value
        if value == '':
            self.__locus_tag_missing = True
    def set_gene_number(self,value):
        self.__gene_number = value
    def set_product_description(self,value):
        self.__product_description = value
    def set_function_description(self,value):
        self.__function_description = value
    def set_note_description(self,value):
        self.__note_description = value


    # Define all attribute getters:
    def get_locus_tag(self):
        return self.__locus_tag
    def get_gene_number(self):
        return self.__gene_number
    def get_product_description(self):
        return self.__product_description
    def get_function_description(self):
        return self.__function_description
    def get_note_description(self):
        return self.__note_description
    def get_locus_tag_missing(self):
        return self.__locus_tag_missing




class MatchedGenomes:

    # Initialize all attributes:
    def __init__(self):

        # Initialize all non-calculated attributes:
        self.__phamerator_genome = ''
        self.__phagesdb_genome = ''
        self.__ncbi_genome = ''

        #Phamerator and NCBI matched data comparison results
        self.__phamerator_ncbi_sequence_mismatch = False
        self.__phamerator_ncbi_sequence_length_mismatch = False
        self.__ncbi_record_header_fields_phage_name_mismatch = False
        self.__ncbi_host_mismatch = False
        self.__phamerator_ncbi_perfect_matched_features = [] #List of MatchedCdsFeature objects
        self.__phamerator_ncbi_imperfect_matched_features = [] #List of MatchedCdsFeature objects
        self.__phamerator_features_unmatched_in_ncbi = [] #List of CdsFeature objects
        self.__ncbi_features_unmatched_in_phamerator = [] #List of CdsFeature objects
        self.__phamerator_ncbi_perfect_matched_features_tally = 0
        self.__phamerator_ncbi_imperfect_matched_features_tally = 0
        self.__phamerator_features_unmatched_in_ncbi_tally = 0
        self.__ncbi_features_unmatched_in_phamerator_tally = 0
        self.__phamerator_ncbi_different_descriptions_tally = 0
        self.__phamerator_ncbi_different_translation_tally = 0



        #Phamerator and phagesdb matched data comparison results
        self.__phamerator_phagesdb_sequence_mismatch = False
        self.__phamerator_phagesdb_sequence_length_mismatch = False
        self.__phamerator_phagesdb_host_mismatch = False
        self.__phamerator_phagesdb_accession_mismatch = False
        self.__phamerator_phagesdb_cluster_subcluster_mismatch = False


        #phagesdb and NCBI matched data comparison results
        self.__phagesdb_ncbi_sequence_mismatch = False
        self.__phagesdb_ncbi_sequence_length_mismatch = False





    # Define all attribute setters:
    def set_phamerator_genome(self,value):
        self.__phamerator_genome = value
    def set_phagesdb_genome(self,value):
        self.__phagesdb_genome = value
    def set_ncbi_genome(self,value):
        self.__ncbi_genome = value

    def compare_phamerator_ncbi_genomes(self):

        #verify that there is a Phamerator and NCBI genome in the matched genome object
        ph_genome = self.__phamerator_genome
        ncbi_genome = self.__ncbi_genome

        if ph_genome == '' or ncbi_genome == '':
            ###Set object variables to some default value
            pass
        else:

            if ph_genome.get_sequence() != ncbi_genome.get_sequence():
                self.__phamerator_ncbi_sequence_mismatch = True
            if ph_genome.get_length() != ncbi_genome.get_length():
                self.__phamerator_ncbi_sequence_length_mismatch = True


            #Compare phage names
            pattern1 = re.compile('^' + ph_genome.get_phage_name() + '$')
            pattern2 = re.compile('^' + ph_genome.get_phage_name())

            if find_name(pattern2,ncbi_genome.get_record_description.split(' ')) == 0 or \
                find_name(pattern1,ncbi_genome.get_record_source.split(' ')) == 0 or \
                find_name(pattern1,ncbi_genome.get_record_organism.split(' ')) == 0 or \
                find_name(pattern1,ncbi_genome.get_source_feature_organism.split(' ')) == 0:

                self.__ncbi_record_header_fields_phage_name_mismatch = True



            #Compare host data
            search_host = ph_genome.get_host
            if search_host == 'Mycobacterium':
                search_host = search_host[:-3]
            pattern3 = re.compile('^' + search_host)


            if (find_name(pattern3,ncbi_genome.get_record_description().split(' ')) == 0 or \
                find_name(pattern3,ncbi_genome.get_record_source().split(' ')) == 0 or \
                find_name(pattern3,ncbi_genome.get_record_organism().split(' ')) == 0 or \
                find_name(pattern3,ncbi_genome.get_source_feature_organism().split(' ')) == 0 or \
                (ncbi_genome.get_source_feature_host() != '' and find_name(pattern3,ncbi_genome.get_source_feature_host().split(' ')) == 0) or \
                (ncbi_genome.get_source_feature_lab_host() != '' and find_name(pattern3,ncbi_genome.get_source_feature_lab_host().split(' ')) == 0):

                self.__ncbi_host_mismatch = True


            #Compare CDS features

            ph_cds_data = ph_genome.get_cds_dict()
            ncbi_cds_data = ncbi_genome.get_cds_dict()

            ph_cds_id_set = ph_cds_data.keys()
            ncbi_cds_id_set = ncbi_cds_data.keys()

            #Create the matched and unmatched sets
            unmatched_ph_cds_id_set = ph_cds_id_set - ncbi_cds_id_set
            unmatched_ncbi_cds_id_set = ncbi_cds_id_set - ph_cds_id_set
            perfect_matched_cds_id_set = ph_cds_id_set & ncbi_cds_id_set

            #From the unmatched sets, created refined cds_id sets
            ph_cds_end_strand_id_dict = {} #Key = end, strand tuple; #Value = start, end, strand tuple
            ph_duplicate_end_strand_id_list = []
            for element in unmatched_ph_cds_id_set:
                element_end_strand_tup = (element[1],element[2])
                if element_end_strand_tup not in ph_cds_end_strand_id_dict.keys():
                    ph_cds_end_strand_id_dict[element_end_strand_tup] = element
                else:
                    ###Need to improve this error handling
                    ph_duplicate_end_strand_id_list.append(element)
                    print 'Error: duplicate end_strand id'
                    raw_input()
            #Now go back and remove the elements with dupicate ids
            for element in ph_duplicate_end_strand_id_list:
                ph_cds_end_strand_id_dict.pop(element)
                ###Pop elements from dict. Make sure this function works right

            ncbi_cds_end_strand_id_dict = {} #Key = end, strand tuple; #Value = start, end, strand tuple
            ncbi_duplicate_end_strand_id_list = []
            for element in unmatched_ncbi_cds_id_set:
                element_end_strand_tup = (element[1],element[2])
                if element_end_strand_tup not in ncbi_cds_end_strand_id_dict.keys():
                    ncbi_cds_end_strand_id_dict[element_end_strand_tup] = element
                else:
                    ###Need to improve this error handling
                    ncbi_duplicate_end_strand_id_list.append(element)
                    print 'Error: duplicate end_strand id'
                    raw_input()
            #Now go back and remove the elements with dupicate ids
            for element in ncbi_duplicate_end_strand_id_list:
                ncbi_cds_end_strand_id_dict.pop(element)
                ###Pop elements from dict. Make sure this function works right

###Create a function to create the end-strand dictionaries, since the code block is duplicated

            #Using only the end_strand tuple data of the unmatched features, see if additional features can be matched
            ph_cds_second_id_set = ph_cds_end_strand_id_dict.keys()
            ncbi_cds_second_id_set = ncbi_cds_end_strand_id_dict.keys()
            second_unmatched_ph_cds_id_set = ph_cds_second_id_set - ncbi_cds_second_id_set
            second_unmatched_ncbi_cds_id_set = ncbi_cds_second_id_set - ph_cds_second_id_set
            imperfect_matched_cds_id_set = ph_cds_second_id_set | ncbi_cds_second_id_set


            #Create MatchedCdsFeatures objects
            for start_end_strand_tup in perfect_matched_cds_id_set:
                matched_cds_object = MatchedCdsFeatures()
                matched_cds_object.set_phamerator_feature(ph_cds_data[start_end_strand_tup])
                matched_cds_object.set_ncbi_feature(ncbi_cds_data[start_end_strand_tup])
                self.__phamerator_ncbi_perfect_matched_features.append(matched_cds_object)

            for end_strand_tup in imperfect_matched_cds_id_set:
                ph_start_end_strand_tup = ph_cds_end_strand_id_dict[end_strand_tup]
                ncbi_start_end_strand_tup = ncbi_cds_end_strand_id_dict[end_strand_tup]
                matched_cds_object = MatchedCdsFeatures()
                matched_cds_object.set_phamerator_feature(ph_cds_data[ph_start_end_strand_tup])
                matched_cds_object.set_ncbi_feature(ncbi_cds_data[ncbi_start_end_strand_tup])
                self.__phamerator_ncbi_imperfect_matched_features.append(matched_cds_object)

            for end_strand_tup in second_unmatched_ph_cds_id_set:
                start_end_strand_tup = ph_cds_end_strand_id_dict[end_strand_tup]
                self.__phamerator_features_unmatched_in_ncbi.append(ph_cds_data[start_end_strand_tup])

            for end_strand_tup in second_unmatched_ncbi_cds_id_set:
                start_end_strand_tup = ncbi_cds_end_strand_id_dict[end_strand_tup]
                self.__ncbi_features_unmatched_in_phamerator.append(ncbi_cds_data[start_end_strand_tup])


            #Now compute the number of features in each category
            self.__phamerator_ncbi_perfect_matched_features_tally = len(self.__phamerator_ncbi_perfect_matched_features)
            self.__phamerator_ncbi_imperfect_matched_features_tally = len(self.__phamerator_ncbi_imperfect_matched_features)
            self.__phamerator_features_unmatched_in_ncbi_tally = len(self.__phamerator_features_unmatched_in_ncbi)
            self.__ncbi_features_unmatched_in_phamerator_tally = len(self.__ncbi_features_unmatched_in_phamerator)

            #Now compare gene descriptions and translations for perfectly matched cds features
            for matched_cds_object in self.__phamerator_ncbi_perfect_matched_features:
                matched_cds_object.compare_phamerator_ncbi_cds_features()
                if matched_cds_object.get_phamerator_ncbi_different_translations():
                    self.__phamerator_ncbi_different_translation_tally += 1
                if matched_cds_object.get_phamerator_ncbi_different_descriptions():
                    self.__phamerator_ncbi_different_descriptions_tally += 1

            #Compare gene descriptions for imperfectly matched cds features
            #Since imperfect matches means different start site, the translation will be different by default
            for matched_cds_object in self.__phamerator_ncbi_imperfect_matched_features:
                matched_cds_object.compare_phamerator_ncbi_cds_features()
                if matched_cds_object.get_phamerator_ncbi_different_descriptions():
                    self.__phamerator_ncbi_different_descriptions_tally += 1


    def compare_phamerator_phagesdb_genomes(self):

        #verify that there is a Phamerator and phagesdb genome in the matched genome object
        ph_genome = self.__phamerator_genome
        pdb_genome = self.__phagesdb_genome

        if ph_genome == '' or pdb_genome == '':
            ###Set object variables to some default value
            pass
        else:

            if ph_genome.get_sequence() != pdb_genome.get_sequence():
                self.__phamerator_phagesdb_sequence_mismatch = True
            if ph_genome.get_length() != pdb_genome.get_length():
                self.__phamerator_phagesdb_sequence_length_mismatch = True
            if ph_genome.get_accession() != pdb_genome.get_accession():
                self.__phamerator_phagesdb_accession_mismatch = True
            if ph_genome.get_host() != pdb_genome.get_host():
                self.__phamerator_phagesdb_host_mismatch = True
            if ph_genome.get_cluster_subcluster() != pdb_genome.get_cluster() and \
                ph_genome.get_cluster_subcluster() != pdb_genome.get_subcluster():

                self.__phamerator_phagesdb_cluster_subcluster_mismatch = True



    def compare_phagesdb_ncbi_genomes(self):

        #verify that there is a phagesdb and NCBI genome in the matched genome object
        pdb_genome = self.__phagesdb_genome
        ncbi_genome = self.__ncbi_genome

        if pdb_genome == '' or ncbi_genome == '':
            ###Set object variables to some default value
            pass
        else:
            if pdb_genome.get_sequence() != ncbi_genome.get_sequence():
                self.__phagesdb_ncbi_sequence_mismatch = True
            if pdb_genome.get_length() != ncbi_genome.get_length():
                self.__phagesdb_ncbi_sequence_length_mismatch = True



        # Define all attribute getters:
        def get_phamerator_genome(self):
            return self.__phamerator_genome
        def get_phagesdb_genome(self):
            return self.__phagesdb_genome
        def get_ncbi_genome(self):
            return self.__ncbi_genome
        def get_phamerator_ncbi_sequence_mismatch(self):
            return self.__phamerator_ncbi_sequence_mismatch
        def get_phamerator_ncbi_perfect_matched_features(self):
            self.__phamerator_ncbi_perfect_matched_features
        def get_phamerator_ncbi_imperfect_matched_features(self):
            self.__phamerator_ncbi_imperfect_matched_features
        def get_phamerator_features_unmatched_in_ncbi(self):
            self.__phamerator_features_unmatched_in_ncbi
        def get_ncbi_features_unmatched_in_phamerator(self):
            self.__ncbi_features_unmatched_in_phamerator
        def get_phamerator_ncbi_perfect_matched_features_tally(self):
            self.__phamerator_ncbi_perfect_matched_features_tally
        def get_phamerator_ncbi_imperfect_matched_features_tally(self):
            self.__phamerator_ncbi_imperfect_matched_features_tally
        def get_phamerator_features_unmatched_in_ncbi_tally(self):
            self.__phamerator_features_unmatched_in_ncbi_tally
        def get_ncbi_features_unmatched_in_phamerator_tally(self):
            self.__ncbi_features_unmatched_in_phamerator_tally
        def get_phamerator_ncbi_sequence_length_mismatch(self):
            return self.__phamerator_ncbi_sequence_length_mismatch
        def get_ncbi_record_header_fields_phage_name_mismatch(self):
            return self.__ncbi_record_header_fields_phage_name_mismatch
        def get_ncbi_host_mismatch(self):
            return self.__ncbi_host_mismatch
        def get_phamerator_ncbi_different_descriptions_tally(self):
            return self.__phamerator_ncbi_different_descriptions_tally
        def get_phamerator_ncbi_different_translation_tally(self):
            return self.__phamerator_ncbi_different_translation_tally

        def get_phagesdb_ncbi_sequence_mismatch(self):
            return self.__phagesdb_ncbi_sequence_mismatch
        def get_phagesdb_ncbi_sequence_length_mismatch(self):
            return self.__phagesdb_ncbi_sequence_length_mismatch

        def get_phamerator_phagesdb_sequence_mismatch(self):
            return self.__phamerator_phagesdb_sequence_mismatch
        def get_phamerator_phagesdb_sequence_length_mismatch(self):
            return self.__phamerator_phagesdb_sequence_length_mismatch
        def get_phamerator_phagesdb_host_mismatch(self):
            return self.__phamerator_phagesdb_host_mismatch
        def get_phamerator_phagesdb_accession_mismatch(self):
            return self.__phamerator_phagesdb_accession_mismatch
        def get_phamerator_phagesdb_cluster_subcluster_mismatch(self):
            return self.__phamerator_phagesdb_cluster_subcluster_mismatch



class MatchedCdsFeatures:

    # Initialize all attributes:
    def __init__(self):

        # Initialize all non-calculated attributes:
        self.__phamerator_feature = ''
        self.__ncbi_feature = ''

        #Matched data comparison results
        self.__phamerator_ncbi_different_translation = False #True = there are different translations
        self.__phamerator_ncbi_different_start_sites = False #True = there are different start sites
        self.__phamerator_ncbi_different_descriptions = False #True = there are different gene descriptions


        # Define all attribute setters:
        def set_phamerator_feature(self,value):
            self.__phamerator_feature = value
        def set_ncbi_feature(self,value):
            self.__ncbi_feature = value


        def compare_phamerator_ncbi_cds_features(self):

            if self.__phamerator_feature.get_left_boundary() != self.__ncbi_feature.get_left_boundary():
                self.__phamerator_ncbi_different_start_sites = True

            if self.__phamerator_feature.get_notes() != self.__ncbi_feature.get_product_description() and \
                self.__phamerator_feature.get_notes() != self.__ncbi_feature.get_function_description() and \
                self.__phamerator_feature.get_notes() != self.__ncbi_feature.get_note_description():

                self.__phamerator_ncbi_different_descriptions = True

            if self.__phamerator_feature.get_translation() != self.__ncbi_feature.get_translation():
                self.__phamerator_ncbi_different_translations = True

        # Define all attribute getters:
        def get_phamerator_feature(self):
            return self.__phamerator_feature
        def get_ncbi_feature(self):
            return self.__ncbi_feature
        def get_phamerator_ncbi_different_start_sites(self):
            return self.__different_start_sites
        def get_phamerator_ncbi_different_descriptions(self):
            return self.__different_descriptions
        def get_phamerator_ncbi_different_translations(self):
            return self.__different_translations

























###Mainline code

#Get the command line parameters
try:
    database = sys.argv[1] #What Phamerator database should be compared to phagesdb?
    output_dir = sys.argv[2] #What is the directory into which the report should go
except:
    print "\n\n\
            This is a python script to compare the Phamerator, phagesdb, and NCBI databases for inconsistencies.\n\
            It requires two arguments:\n\
            First argument: name of MySQL database that will be checked (e.g. 'Actino_Draft').\n\
            Second argument: directory path to where the consistency report should be made (csv-formatted).\n\"
    sys.exit(1)

#Expand home directory
home_dir = os.path.expanduser('~')


#Verify the folder exists

#Add '/' at the end if it's not there
if output_dir[-1] != "/":
    output_dir = output_dir + "/"


#Expand the path if it references the home directory
if output_dir[0] == "~":
    output_dir = home_dir + output_dir[1:]

#Expand the path, to make sure it is a complete directory path (in case user inputted path with './path/to/folder')
output_dir = os.path.abspath(output_dir)


if os.path.isdir(output_dir) == False:
    print "\n\nInvalid output folder.\n\n"
    sys.exit(1)







#Set up MySQL parameters
mysqlhost = 'localhost'
print "\n\n"
username = getpass.getpass(prompt='mySQL username:')
print "\n\n"
password = getpass.getpass(prompt='mySQL password:')
print "\n\n"


#Set up NCBI parameters

#Get email infor for NCBI
contact_email = raw_input('Provide email for NCBI: ')

batch_size = ''
batch_size_valid = False
while batch_size_valid == False:
    batch_size = raw_input('Record retrieval batch size (must be greater than 0 and recommended is 100-200): ')
    print "\n\n"
    if batch_size.isdigit():
        batch_size = int(batch_size)
        if batch_size > 0:
            batch_size_valid = True
        else:
            print 'Invalid choice.''
            print "\n\n"
    else:
        print 'Invalid choice.''
        print "\n\n"

#Determine which type of updates will be performed.
save_ncbi_records = select_option("\nDo you want to save retrieved NCBI records to disk? (yes or no) ")

#You have to specify how many results to return at once. If you set it to 1 page long and 100,000 genomes/page, then this will return everything
pdb_sequenced_phages_url = "http://phagesdb.org/api/sequenced_phages/?page=1&page_size=100000"

#Set up dna and protein alphabets to verify sequence integrity
dna_alphabet_set = set(IUPAC.IUPACUnambiguousDNA.letters)
protein_alphabet_set = set(IUPAC.ExtendedIUPACProtein.letters)




#Create output directories
date = time.strftime("%Y%m%d")

main_output_folder = '%s_database_comparison' % date
main_output_path = os.path.join(output_dir,main_output_folder)


try:
    os.mkdir(main_output_path)
except:
    print "\nUnable to create output folder: %s" % main_output_path
    sys.exit(1)

os.chdir(main_output_path)



#Create a folder to store NCBI records
if save_ncbi_records == 'y':
    ncbi_output_folder = '%s_ncbi_records' % date
    ncbi_output_path = os.path.join(output_dir,ncbi_output_folder)
    os.mkdir(ncbi_output_path)

#Create list to hold all open file handles
file_handle_list = []


#Retrieve database version
#Retrieve current genome data in database
#0 = PhageID
#1 = Name
#2 = HostStrain
#3 = Sequence
#4 = Length
#5 = status
#6 = Cluster
#7 = Accession
#8 = auto-update NCBI record flag
#Retrieve current gene data in database
#0 = PhageID
#1 = GeneID
#2 = Name
#3 = Start
#4 = Stop
#5 = Orientation
#6 = Translation
#7 = Notes


try:
    con = mdb.connect(mysqlhost, username, password, database)
    con.autocommit(False)
    cur = con.cursor()
except:
    print 'Unsuccessful attempt to connect to the database. Please verify the database, username, and password.'
    report_file.close()
    sys.exit(1)

try:
    cur.execute("START TRANSACTION")
    cur.execute("SELECT version FROM version")
    ph_version = str(cur.fetchone()[0])
    cur.execute("SELECT PhageID,Name,HostStrain,Sequence,SequenceLength,status,Cluster,Accession,RetrieveRecord FROM phage")
    ph_genome_data_tuples = cur.fetchall()
    cur.execute("SELECT PhageID,GeneID,Name,Start,Stop,Orientation,Translation,Notes from gene")
    ph_gene_data_tuples = cur.fetchall()
    cur.execute("COMMIT")
    cur.close()
    con.autocommit(True)

except:
    mdb_exit("\nUnable to access the database to retrieve genome information.\nNo changes have been made to the database.")

con.close()

#write_out(report_file,"\nPhamerator database: " + database)
#write_out(report_file,"\nPhamerator database version: " + db_version)








#Variable to track number of warnings and total_errors encountered
warnings = 0
total_errors = 0

#Create data sets
phageId_set = set()
phageName_set = set()
phageHost_set = set()
phageStatus_set = set()
phageCluster_set = set()
print 'Preparing genome data sets from the phamerator database...'
ph_genome_object_dict = {} #Key = PhageID; #Value = genome_object
ph_search_name_set = set()
ph_search_name_duplicate_set = set()
ph_accession_set = set()
ph_accession_duplicate_set = set()
for genome_tuple in ph_genome_data_tuples:


    genome_object = PhameratorGenome()
    genome_object.set_phage_id(genome_tuple[0])
    genome_object.set_phage_name(genome_tuple[1])
    genome_object.set_host(genome_tuple[2])
    genome_object.set_sequence(genome_tuple[3])
    genome_object.set_status(genome_tuple[5])
    genome_object.set_cluster_subcluster(genome_tuple[6])
    genome_object.set_accession(genome_tuple[7])
    genome_object.set_ncbi_update_flag(genome_tuple[8])
    genome_object.compute_nucleotide_errors(dna_alphabet_set)
    genome_object.compute_cds_feature_errors()
    ph_genome_objects[genome_tuple[0]] = genome_object

    #This keeps track of whether there are duplicate phage names that will be used
    #to match up to phagesdb data.
    if genome_object.get_search_name() in ph_search_name_set:
        ph_search_name_duplicate_set.add(genome_object.get_search_name())
    else:
        ph_search_name_set.add(genome_object.get_search_name())

    #This keeps track of whether there are duplicate accession numbers that will be
    #used to match up to NCBI data
    if genome_object.get_accession() != '':
        if genome_object.get_accession() in ph_accession_set:
            ph_accession_duplicate_set.add(genome_object.get_accession())
        else:
            ph_accession_set.add(genome_object.get_accession())



#phagesdb relies on the phageName, and not the phageID. But Phamerator does not require phageName values to be unique.
#Check if there are any phageName duplications. If there are, they will not be able to be compared to phagesdb data.
if len(ph_search_name_duplicate_set) > 0:
    print 'Warning: Data is not able to be matched to phagesdb because of the following non-unique phage Names in phamerator:'
    for element in ph_search_name_duplicate_set:
        print element
    raw_input('Press ENTER to proceed')
    ###Add a sys.exit line???

#Phamerator accessions aren't unique, so there could be duplicates
if len(ph_accession_duplicate_set) > 0:
    print 'Warning: There are duplicate accessions in Phamerator. Unable to proceed with NCBI record retrieval.'
    for accession in ph_accession_duplicate_set:
        print accession
        ph_accession_set.pop(accession)
    raw_input('Press ENTER to proceed')
    ###Add a sys.exit line???






ph_gene_objects_list = []
ph_gene_data_phage_id_set = set()
for gene_tuple in ph_gene_data_tuples:

    ph_gene_data_phage_id_set.add(gene_tuple[0])

    gene_object = PhameratorFeature()
    gene_object.set_phage_id(gene_tuple[0])
    gene_object.set_gene_id(gene_tuple[1])
    gene_object.set_gene_name(gene_tuple[2])
    gene_object.set_type_id('CDS')
    gene_object.set_left_boundary(gene_tuple[3])
    gene_object.set_right_boundary(gene_tuple[4])
    gene_object.set_strand(gene_tuple[5])
    gene_object.set_translation(gene_tuple[6])
    gene_object.set_notes(retrieve_description(gene_tuple[7]))
    gene_object.set_search_id()
    gene_object.set_search_name()
    gene_object.compute_amino_acid_errors(protein_alphabet_set)
    gene_object.set_start_end_strand_id()
    gene_object.compute_boundary_error()
    ph_gene_objects_list.append(gene_object)


#ph_gene_objects_dict = {} #Key = PhageID; #Value = list of gene objects
for phage_id in ph_genome_object_dict.keys():
    genome_object = ph_genome_object_dict[phage_id]
    new_gene_object_list = []
    for gene_object in ph_gene_objects_list:
        if gene_object.get_phage_id() == phage_id:
            new_gene_object_list.append(gene_object)

    genome_object.set_cds_features(new_gene_object_list)



#Now retrieve all phagesdb data


#Retrieve a list of all sequenced phages listed on phagesdb
#You have to specify how many results to return at once. If you set it to 1 page long and 100,000 genomes/page, then this will return everything
print 'Retrieving data from phagesdb...'
pdb_sequenced_phages_url = "http://phagesdb.org/api/sequenced_phages/?page=1&page_size=100000"
pdb_sequenced_phages_json = urllib.urlopen(pdb_sequenced_phages_url)
pdb_sequenced_phages_dict = json.loads(pdb_sequenced_phages_json.read())
pdb_sequenced_phages_json.close()

#Data for each phage is stored in a dictionary per phage, and all dictionaries are stored in a list under "results"
pdb_genome_dict = {}
pdb_search_name_set = set()
pdb_search_name_duplicate_set = set()
for element_dict in sequenced_phages_dict['results']:

    genome_object = PhagesdbGenome()

    #Name, Host, Accession
    genome_object.set_phage_name(element_dict['phage_name'])
    genome_object.set_host(element_dict['isolation_host']['genus'])
    genome_object.set_accession(element_dict['genbank_accession'])

    #Cluster
    if element_dict['pcluster'] is not None:
        #Sometimes cluster information is not present. In the phagesdb database, it is recorded as NULL.
        #When phages data is downloaded from phagesdb, NULL cluster data is converted to "Unclustered".
        #In these cases, leave cluster as ''
        genome_object.set_cluster(element_dict['pcluster']['cluster'])

    #Subcluster
    if element_dict['psubcluster'] is not None:
        #A phage may be clustered but not subclustered.
        #In these cases, leave subcluster as ''
        genome_object.set_subcluster(element_dict['psubcluster']['subcluster'])

    #Check to see if there is a fasta file stored on phagesdb for this phage
    if element_dict['fasta_file'] is not None:
        fastafile_url = element_dict['fasta_file']

        response = urllib2.urlopen(fastafile_url)
        retrieved_fasta_file = response.read()
        response.close()

        #All sequence rows in the fasta file may not have equal widths, so some processing of the data is required
        #If you split by newline, the header is retained in the first list element
        split_fasta_data = retrieved_fasta_file.split('\n')
        pdb_sequence = ''
        index = 1
        while index < len(split_fasta_data):
            pdb_sequence = pdb_sequence + split_fasta_data[index].strip() #Strip off potential whitespace before appending, such as '\r'
            index += 1
        genome_object.set_sequence(pdb_sequence)
        genome_object.compute_nucleotide_errors(dna_alphabet_set)

    pdb_search_name = genome_object.get_search_name()
    if pdb_search_name in pdb_search_name_set:
        pdb_search_name_duplicate_set.add(pdb_search_name)
    else:
        pdb_search_name_set.add(pdb_search_name)
        pdb_genome_dict[pdb_search_name] = element_dict



#phagesdb phage names are unique, but just make sure after they are converted to a search name
if len(pdb_search_name_duplicate_set) > 0:
    print 'Warning: phagesdb data is not able to be matched because of the following non-unique phage names in phagesdb:'
    for element in pdb_search_name_duplicate_set:
        print element
    raw_input('Press ENTER to proceed')
    ###Add a sys.exit line???


#Make sure all sequenced phage data has been retrieved
if (len(pdb_sequenced_phages_dict['results']) != pdb_sequenced_phages_dict['count'] or \
    len(pdb_sequenced_phages_dict['results']) != len(pdb_genome_dict)):

    print "\nUnable to retrieve all phage data from phagesdb due to default retrieval parameters."
    print 'Update parameters in script to enable these functions.'
    raw_input('Press ENTER to proceed')
    ###Add a sys.exit line?




print "\n\nRetrieving updated records from NCBI"


ph_accession_set

#Use esearch to verify the accessions are valid and efetch to retrieve the record
Entrez.email = contact_email
Entrez.tool = 'NCBIRecordRetrievalScript'



#Create batches of accessions
accession_retrieval_list = list(ph_accession_set)

#Add [ACCN] field to each accession number
index = 0
while index < len(accession_retrieval_list):
    accession_retrieval_list[index] = accession_retrieval_list[index] + "[ACCN]"
    index += 1

#Keep track of specific records
retrieved_record_list = []
retrieval_error_list = []



#When retrieving in batch sizes, first create the list of values indicating which indices of the unique_accession_list should be used to create each batch
#For instace, if there are five accessions, batch size of two produces indices = 0,2,4
for batch_index_start in range(0,len(accession_retrieval_list),batch_size):


    if batch_index_start + batch_size > len(accession_retrieval_list):
        batch_index_stop = len(accession_retrieval_list)
    else:
        batch_index_stop = batch_index_start + batch_size

    current_batch_size = batch_index_stop - batch_index_start
    delimiter = " | "
    esearch_term = delimiter.join(unique_accession_list[batch_index_start:batch_index_stop])


    #Use esearch for each accession
    search_handle = Entrez.esearch(db = 'nucleotide', term = esearch_term,usehistory='y')
    search_record = Entrez.read(search_handle)
    search_count = int(search_record['Count'])
    search_webenv = search_record['WebEnv']
    search_query_key = search_record['QueryKey']



    #Keep track of the accessions that failed to be located in NCBI
    if search_count < current_batch_size:
        search_accession_failure = search_record['ErrorList']['PhraseNotFound']

        #Each element in this list is formatted "accession[ACCN]"
        for element in search_accession_failure:
            retrieval_error_list.append(element[:-6])



    #Now retrieve all records using efetch
    fetch_handle = Entrez.efetch(db = 'nucleotide', \
                                rettype = 'gb', \
                                retmode = 'text', \
                                retstart = 0, \
                                retmax = search_count, \
                                webenv = search_webenv, \
                                query_key = search_query_key)
    fetch_records = SeqIO.parse(fetch_handle,'genbank')

    for record in fetch_records:

        retrieved_record_list.append(record)

    search_handle.close()
    fetch_handle.close()



#Report the accessions that could not be retrieved.
failed_accession_report_fh = open(os.path.join(main_output_path,date + '_failed_accession_retrieval.csv'), 'w')
failed_accession_report_writer = csv.writer(failed_accession_report_fh)
failed_accession_report_writer.writerow(date + '' Database comparison')
failed_accession_report_writer.writerow('Accessions unable to be retrieved from NCBI')
for retrieval_error_accession in retrieval_error_list:
    failed_accession_report_writer.writerow(retrieval_error_accession)
failed_accession_report_fh.close()




ncbi_genome_dict = {} #Key = accession; #Value = genome data
for retrieved_record in retrieved_record_list:

    genome_object = NcbiGenome()

    try:
        genome_object.set_record_name(retrieved_record.name)
    except:
        genome_object.set_record_name('')

    try:
        genome_object.set_record_id(retrieved_record.id)
    except:
        genome_object.set_record_id('')

    try:
        #There may be a list of accessions associated with this file. I think the first accession in the list is the most recent.
        #Discard the version suffix if it is present in the Accession field (it might not be present)
        record_accession = retrieved_record.annotations['accessions'][0]
        record_accession = record_accession.split('.')[0]
        genome_object.set_record_accession(record_accession)
    except:
        genome_object.set_record_accession('')

    try:
        genome_object.set_record_description(retrieved_record.description)
    except:
        genome_object.set_record_description('')

    try:
        genome_object.set_record_source(retrieved_record.annotations['source'])
    except:
        genome_object.set_record_source('')

    try:
        record_organism = retrieved_record.annotations['organism']
        if record_organism.split(' ')[-1] == 'Unclassified.':
            genome_object.set_record_organism(record_organism.split(' ')[-2])
        else:
            genome_object.set_record_organism(record_organism.split(' ')[-1])
    except:
        genome_object.set_record_organism('')

    genome_object.set_sequence(retrieved_record.seq)
    genome_object.compute_nucleotide_errors(dna_alphabet_set)


    #Iterate through all features
    source_feature_list = []
    ncbi_cds_features = []

    #A good bit of the code for parsing features is copied from import_phage.py
    for feature in retrieved_record.features:

        gene_object = NcbiCdsFeature()


        if feature.type != 'CDS':
            #Retrieve the Source Feature info
            if feature.type == 'source':
                source_feature_list.append(feature)

        else:

            #Feature type
            gene_object.set_type_id('CDS')

            #Locus tag
            try:
                gene_object.set_locus_tag(feature.qualifiers['locus_tag'][0])
            except:
                pass

            #Orientation
            if feature.strand == 1:
                gene_object.set_strand('forward')
            elif feature.strand == -1:
                gene_object.set_strand('reverse')
            #ssRNA phages
            elif feature.strand is None:
                gene_object.set_strand('forward')


            #Gene boundary coordinates
            #Compound features are tricky to parse.
            if str(feature.location)[:4] == 'join':

                #Skip this compound feature if it is comprised of more than two features (too tricky to parse).
                if len(feature.location.parts) <= 2:
                    #Retrieve compound feature positions based on strand
                    if feature.strand == 1:
                        gene_object.set_left_boundary(str(feature.location.parts[0].start))
                        gene_object.set_right_boundary(str(feature.location.parts[1].end))
                    elif feature.strand == -1:
                        gene_object.set_left_boundary(str(feature.location.parts[1].start))
                        gene_object.set_right_boundary(str(feature.location.parts[0].end))
                    #If strand is None...
                    else:
                        pass
                        ###Do I want to pass?
            else:
                gene_object.set_left_boundary(str(feature.location.start))
                gene_object.set_right_boundary(str(feature.location.end))

            #Translation
            try:
                gene_object.set_translation(feature.qualifiers['translation'][0])
            except:
                pass

            #Gene function, note, and product descriptions
            try:
                feature_product = retrieve_description(feature.qualifiers['product'][0])
                gene_object.set_product_description(feature_product)
                if feature_product != '':
                    feature_product_tally += 1
            except:
                pass
            try:
                feature_function = retrieve_description(feature.qualifiers['function'][0])
                gene_object.set_function_description(feature_function)
                if feature_function != '':
                    feature_function_tally += 1
            except:
                pass

            try:
                feature_note = retrieve_description(feature.qualifiers['note'][0])
                gene_object.set_note_description(feature_note)
                if feature_note != '':
                    feature_note_tally += 1
            except:
                pass

            #Gene number
            try:
                gene_object.set_gene_number(feature.qualifiers['gene'][0])
            except:
                pass

            #Compute other fields
            gene_object.set_search_name()
            gene_object.compute_amino_acid_errors(protein_alphabet_set)
            gene_object.set_start_end_strand_id()
            gene_object.compute_boundary_error()

            #Now add to full list of gene objects
            ncbi_cds_features.append(gene_object)




    #Set the following variables after iterating through all features

    #If there was one and only one source feature present, parse certain qualifiers
    if len(source_feature_list) == 1:
        try:
            genome_object.set_source_feature_organism(str(feature.qualifiers['organism'][0]))
        except:
            pass
        try:
            genome_object.set_source_feature_host(str(feature.qualifiers['host'][0]))
        except:
            pass
        try:
            genome_object.set_source_feature_lab_host(str(feature.qualifiers['lab_host'][0]))
        except:
            pass

    genome_object.set_cds_features(ncbi_cds_features)
    genome_object.compute_cds_feature_errors()
    genome_object.compute_ncbi_cds_feature_errors()


    #After parsing all data, add to the ncbi dictionary
    ncbi_genome_dict[genome_object.get_accession()] = genome_object

    #If selected by user, save retrieved record to file
    if save_ncbi_records == 'yes':
        ncbi_filename = phamerator_name.lower() + '__' + retrieved_record_accession + '.gb'
        SeqIO.write(retrieved_record,os.path.join(ncbi_output_path,ncbi_filename),'genbank')




#Now that all NCBI and phagesdb data is retrieved, match up to Phamerator genome data

ph_unmatched_to_pdb_genomes = [] #List of the phamerator genome objects with no phagesdb matches
ph_unmatched_to_ncbi_genomes = [] #List of the phamerator genome objects with no NCBI matches

#Iterate through each phage in Phamerator
matched_genomes_list = [] #Will store a list of MatchedGenomes objects

for phage_id in ph_genome_object_dict.keys():


    phamerator_genome = ph_genome_object_dict[phage_id]
    matched_objects = MatchedGenomes()
    matched_objects.set_phamerator_genome(phamerator_genome)

    #Match up phagesdb genome
    #First try to match up the phageID, and if that doesn't work, try to match up the phageName
    if phamerator_genome.get_search_id() in pdb_genome_dict.keys():
        pdb_genome = pdb_genome_dict[phamerator_genome.get_search_id()]

    elif phamerator_genome.get_search_name() in pdb_genome_dict.keys():
        pdb_genome = pdb_genome_dict[phamerator_genome.get_search_name()]

    else:
        pdb_genome = ''
        ph_unmatched_to_pdb_genomes.append(phamerator_genome)

    matched_objects.set_phagesdb_genome(pdb_genome)

    #Now match up NCBI genome
    if phamerator_genome.get_accession() != '':
        try:
            ncbi_genome = ncbi_genome_dict[phamerator_genome.get_accession()]
        except:
            ncbi_genome = ''
    else:
        ncbi_genome = ''
        ph_unmatched_to_ncbi_genomes.append(phamerator_genome)

    matched_genomes_list.append(matched_object)

#Output unmatched data to file
unmatched_genome_output_fh = open(os.path.join(main_output_path,date + '_database_comparison_unmatched_genomes.csv'), 'w')
unmatched_genome_output_writer = csv.writer(unmatched_genome_output_fh)
unmatched_genome_output_writer.writerow(date + ' Database comparison')
unmatched_genome_output_writer.writerow('The following Phamerator genomes were not matched to phagesdb:')
unmatched_genome_output_writer.writerow('PhageID','PhageName','Status')
for element in ph_unmatched_to_pdb_genomes:
    unmatched_genome_output_writer.writerow([element.get_phage_id(),\
                                                element.get_phage_name(),\
                                                element.get_status()])
unmatched_genome_output_writer.writerow('The following Phamerator genomes were not matched to NCBI:')
unmatched_genome_output_writer.writerow('PhageID','PhageName','Status','Accession')
for element in ph_unmatched_to_pdb_genomes:
    unmatched_genome_output_writer.writerow([element.get_phage_id(),\
                                                element.get_phage_name(),\
                                                element.get_status(),\
                                                element.get_accession()])
unmatched_genome_output_fh.close()






###Code-general check: True/False vs 0/1





#Now that all genomes have been matched, iterate through each matched objects
#and run methods to compare the genomes
for matched_genome_object in matched_genomes_list:

    matched_genome_object.compare_phamerator_ncbi_genomes() #This method automatically calls method to match and compare cds features
    matched_genome_object.compare_phamerator_phagesdb_genomes()
    matched_genome_object.compare_phagesdb_ncbi_genomes()









#Now output results
#Open files to record update information
genome_report_fh = open(os.path.join(main_output_path,date + '_database_comparison_genome_output.csv'), 'w')
file_handle_list.append(genome_report_fh)
genome_report_writer = csv.writer(genome_report_fh)
genome_report_writer.writerow(date + ' Database comparison')

gene_report_fh = open(os.path.join(main_output_path,date + '_database_comparison_gene_output.csv'), 'w')
file_handle_list.append(gene_report_fh)
gene_report_writer = csv.writer(gene_report_fh)
gene_report_writer.writerow(date + ' Database comparison')




#Output all data to file
#Iterate through matched objects.
#All genomes are stored in a MatchedGenomes object, even if there are no matches.
#All but a few phages should be matched to phagesdb
#Only half of phages should be matched to NCBI
for matched_genomes in matched_genomes_list:

    genome_data_output = []
    ph_genome = matched_genomes.get_phamerator_genome()
    pdb_genome = matched_genomes.get_phagesdb_genome()
    ncbi_genome = matched_genomes.get_ncbi_genome()



    #Phamerator data
    #General genome data
    genome_data_output.append(ph_genome.get_phage_id())# PhageID
    genome_data_output.append(ph_genome.get_name())# Name
    genome_data_output.append(ph_genome.get_search_id())# search_id
    genome_data_output.append(ph_genome.get_search_name())# search name
    genome_data_output.append(ph_genome.get_status())# status
    genome_data_output.append(ph_genome.get_cluster_subcluster())# cluster_subcluster
    genome_data_output.append(ph_genome.get_host())# Host
    genome_data_output.append(ph_genome.get_accession())# Accession
    genome_data_output.append(ph_genome.get_length())# sequence_length
    genome_data_output.append(ph_genome.get_cds_features_tally())# # genes
    genome_data_output.append(ph_genome.get_ncbi_update_flag())# ncbi_update_flag

    #Genome data checks
    genome_data_output.append(ph_genome.get_nucleotide_errors())# sequence contains std nucleotides?
    genome_data_output.append(ph_genome.get_cds_features_with_translation_error_tally())# # translations with non-std amino acids
    genome_data_output.append(ph_genome.get_cds_feature_boundary_error_tally())# # genes with non-standard start-stops
    genome_data_output.append(ph_genome.get_duplicate_cds_features())# genes with duplicate start, stop, strand


    #Phagesdb data
    if isinstance(pdb_genome,PhagesdbGenome):

        #General genome data
        genome_data_output.append(pdb_genome.get_name())# Name
        genome_data_output.append(pdb_genome.get_search_name())# search name
        genome_data_output.append(pdb_genome.get_cluster())# cluster
        genome_data_output.append(pdb_genome.get_subcluster())# subcluster
        genome_data_output.append(pdb_genome.get_host())# Host
        genome_data_output.append(pdb_genome.get_accession())# Accession
        genome_data_output.append(pdb_genome.get_length())# sequence_length

        #Genome data checks
        genome_data_output.append(pdb_genome.get_nucleotide_errors())# sequence contains std nucleotides?
    else:
        genome_data_output.extend(['','','','','','','',''])



    #NCBI data
    if isinstance(ncbi_genome,NcbiGenome):

        #General genome data
        genome_data_output.append(ncbi_genome.get_record_id())# record_id
        genome_data_output.append(ncbi_genome.get_record_name()# record_name
        genome_data_output.append(ncbi_genome.get_record_accession())# record_accession
        genome_data_output.append(ncbi_genome.get_record_description())# record_description
        genome_data_output.append(ncbi_genome.get_record_source())# record_source
        genome_data_output.append(ncbi_genome.get_record_organism())# record_organism
        genome_data_output.append(ncbi_genome.get_source_feature_organism())# source_feature_organism
        genome_data_output.append(ncbi_genome.get_source_feature_host())# source_feature_host
        genome_data_output.append(ncbi_genome.get_source_feature_lab_host())# source_feature_lab_host
        genome_data_output.append(ncbi_genome.get_length())# sequence_length
        genome_data_output.append(ncbi_genome.get_cds_features_tally())# # genes


        #Genome data checks
        genome_data_output.append(ncbi_genome.get_nucleotide_errors())# sequence contains std nucleotides?
        genome_data_output.append(ncbi_genome.get_cds_features_with_translation_error_tally())# # translations with non-std amino acids
        genome_data_output.append(ncbi_genome.get_cds_feature_boundary_error_tally())# # genes with non-standard start-stops
        genome_data_output.append(ncbi_genome.get_tally_product_descriptions())# # genes with product descriptions
        genome_data_output.append(ncbi_genome.get_tally_function_descriptions())# # genes with function descriptions
        genome_data_output.append(ncbi_genome.get_tally_note_descriptions())# # genes with notes descriptions
        genome_data_output.append(ncbi_genome.get_tally_missing_locus_tags())# # genes with missing locus tags
        genome_data_output.append(ncbi_genome.get_tally_locus_tag_typos())# # genes with locus tag typos
        genome_data_output.append(ncbi_genome.get_duplicate_cds_features())# genes with duplicate start, stop, strand

    else:
        genome_data_output.extend(['','','','','','','','','','',\
                                    '','','','','','','','',''])

    #Phamerator-phagesdb checks
    if isinstance(pdb_genome,PhagesdbGenome):
        genome_data_output.append(matched_genomes.get_phamerator_phagesdb_sequence_mismatch())# sequence
        genome_data_output.append(matched_genomes.get_phamerator_phagesdb_sequence_length_mismatch())# sequence length
        genome_data_output.append(matched_genomes.get_phamerator_phagesdb_cluster_subcluster_mismatch())# cluster_subcluster
        genome_data_output.append(matched_genomes.get_phamerator_phagesdb_accession_mismatch())# accession
        genome_data_output.append(matched_genomes.get_phamerator_phagesdb_host_mismatch())# host
    else:
        genome_data_output.extend(['','','','',''])


    #Phamerator-NCBI checks
    if isinstance(ncbi_genome,NcbiGenome):
        genome_data_output.append(matched_genomes.get_phamerator_ncbi_sequence_mismatch())# sequence
        genome_data_output.append(matched_genomes.get_phamerator_ncbi_sequence_length_mismatch())# sequence length
        genome_data_output.append(matched_genomes.get_ncbi_record_header_fields_phage_name_mismatch())# PhageID or PhageName in record header fields mismatch
        genome_data_output.append(matched_genomes.get_ncbi_host_mismatch())# Host in record header or source feature mismatch
        genome_data_output.append(matched_genomes.get_phamerator_ncbi_perfect_matched_features_tally())# # genes perfectly matched
        genome_data_output.append(matched_genomes.get_phamerator_ncbi_imperfect_matched_features_tally())# # genes imperfectly matched (different start sites)
        genome_data_output.append(matched_genomes.get_phamerator_features_unmatched_in_ncbi_tally())# # Phamerator genes not matched
        genome_data_output.append(matched_genomes.get_ncbi_features_unmatched_in_phamerator_tally())# # NCBI genes not matched
        genome_data_output.append(matched_genomes.get_phamerator_ncbi_different_descriptions_tally())# # genes with Phamerator descriptions not in NCBI description fields
        genome_data_output.append(matched_genomes.get_phamerator_ncbi_different_translation_tally())# # genes perfectly matched with different translations
    else:
        genome_data_output.extend(['','','','','','','','','',''])


    #Output phagesdb-NCBI checks
    if isinstance(pdb_genome,PhagesdbGenome) and isinstance(ncbi_genome,NcbiGenome):
        genome_data_output.append(matched_genomes.get_phagesdb_ncbi_sequence_mismatch())# sequence
        genome_data_output.append(matched_genomes.get_phagesdb_ncbi_sequence_length_mismatch())# sequence length
    else:
        genome_data_output.extend(['',''])

    genome_report_writer.writerow(genome_data_output)


    #Once all matched genome data has been outputted, iterate through all matched gene data

    feature_data_output = [] #Will hold all data for each gene

    perfectly_matched_features = matched_genomes.get_phamerator_ncbi_perfect_matched_features()
    imperfectly_matched_features = matched_genomes.get_phamerator_ncbi_imperfect_matched_features()
    ph_unmatched_features = matched_genomes.get_phamerator_features_unmatched_in_ncbi()
    ncbi_unmatched_features = matched_genomes.get_ncbi_features_unmatched_in_phamerator()

    all_features_list = []
    all_features_list.extend(perfectly_matched_features)
    all_features_list.extend(imperfectly_matched_features)
    all_features_list.extend(ph_unmatched_features)
    all_features_list.extend(ncbi_unmatched_features)



    #Iterate through the list of mixed feature objects
    for mixed_feature_object in all_features_list:

        if isinstance(mixed_feature_object,MatchedCdsFeatures):
            phamerator_feature = mixed_feature_object.get_phamerator_feature()
            ncbi_feature = mixed_feature_object.get_ncbi_feature()
        else:
            phamerator_feature = ''
            ncbi_feature = ''

        #Phamerator feature
        if isinstance(phamerator_feature,PhameratorCdsFeature):

            #General gene data
            feature_data_output.append(phamerator_feature.get_phage_id())# phage_id
            feature_data_output.append(phamerator_feature.get_search_id())# search_id
            feature_data_output.append(phamerator_feature.get_type_id())# type_id
            feature_data_output.append(phamerator_feature.get_gene_id())# gene_id
            feature_data_output.append(phamerator_feature.get_gene_name())# gene_name
            feature_data_output.append(phamerator_feature.get_left_boundary())# left boundary
            feature_data_output.append(phamerator_feature.get_right_boundary())# right boundary
            feature_data_output.append(phamerator_feature.get_strand())# strand
            feature_data_output.append(phamerator_feature.get_translation())# translation
            feature_data_output.append(phamerator_feature.get_translation_length())# translation_length
            feature_data_output.append(phamerator_feature.get_notes())# notes

            #Gene data checks
            feature_data_output.append(phamerator_feature.get_amino_acid_errors())# translation contains std amino acids
            feature_data_output.append(phamerator_feature.get_boundary_error())# contains std start and stop coordinates

        else:
            feature_data_output.extend(['','','','','',\
                                        '','','','','',\
                                        '','',''])


        #NCBI feature
        if isinstance(ncbi_feature,NcbiCdsFeature):

            #General gene data
            feature_data_output.append(ncbi_feature.get_locus_tag())# locus_tag
            feature_data_output.append(ncbi_feature.get_gene_number())# gene_number
            feature_data_output.append(ncbi_feature.get_type_id())# type_id
            feature_data_output.append(ncbi_feature.get_left_boundary())# left boundary
            feature_data_output.append(ncbi_feature.get_right_boundary())# right boundary
            feature_data_output.append(ncbi_feature.get_strand())# strand
            feature_data_output.append(ncbi_feature.get_translation())# translation
            feature_data_output.append(ncbi_feature.get_translation_length())# translation_length
            feature_data_output.append(ncbi_feature.get_product_description())# product description
            feature_data_output.append(ncbi_feature.get_function_description())# function description
            feature_data_output.append(ncbi_feature.get_note_description())# note description

            #Gene data checks
            feature_data_output.append(ncbi_feature.get_amino_acid_errors())# translation contains std amino acids
            feature_data_output.append(ncbi_feature.get_boundary_error())# contains std start and stop coordinates
            feature_data_output.append(ncbi_feature.get_locus_tag_missing())# missing locus tag

        else:
            feature_data_output.extend(['','','','','',\
                                        '','','','','',\
                                        '','','',''])


        #Phamerator-NCBI checks
        if isinstance(mixed_feature_object,MatchedCdsFeatures):
            feature_data_output.append(mixed_feature_object.get_phamerator_ncbi_different_descriptions())# Phamerator description in product, function, or note description
            feature_data_output.append(mixed_feature_object.get_phamerator_ncbi_different_start_sites())# same start site
            feature_data_output.append(mixed_feature_object.get_phamerator_ncbi_different_translations())# same translation
        else:
            feature_data_output.extend(['','',''])


        gene_report_writer.writerow(feature_data_output)













#Close script.
print "\n\n\n\Database comparison script completed."

#close all file handles
close_all_files(file_handle_list)
