# File Name: Haas-UMC750-processor.py
# Description: A Translator/processor converting CLSF to G-Code for the Haas-UM750
# Author: Adam Nguyen
# Date: December 19, 2021
# Note: Units are in inches

import getopt, sys
import itertools
import math
import numpy as np

# If you don't wish to use the command, call your CLSF file 'cls.txt', place it in the same folder
# as this python script, assing the debug variable to be true then run the script.
debug = True

# This is our tool class. It is a simple data structure.
class Tool:
    
    
    tools = {}
    # Static Variables
    # tool_count = 1
    
    # List of Class Attributes
    tool_path = None
    tool = None
    tool_name = None
    tool_data = None
    diameter = None
    lower_radius = None
    taper_angle = None
    tip_angle = None
    line_skip = None
    tool_number = None 
    speed = None
    offset = 0 
    line_start = None
    tool_compensation_type = None 
    
    
    def __init__(self, line):
        current_line = line
        end_line = current_line + 2
        lines = CLSF_to_GCode.CLSF[current_line:end_line]
        
        # Check if tool is described in one or two lines in CLSF
        one_line = True
        
        line_check = lines[1].split('/')
        
        if "TLDATA" in line_check:
            one_line = False
            
        if one_line:
            tool_parameters =  lines[0].split(',')
            
            self.tool_path = tool_parameters[0]
            self.tool_path = self.tool_path.split('/')
            self.tool_path =  self.tool_path[1]
             
            self.tool = tool_parameters[1]
            self.tool_name = tool_parameters[2]
            self.tool_data = tool_parameters[3]
            self.diameter = float(tool_parameters[4])
            self.lower_radius = float(tool_parameters[5])
            self.taper_angle = float(tool_parameters[6])
            self.tip_angle = float(tool_parameters[7])
            
            self.line_skip = 0
            
            
        else:
            tool_parameters_1 =  lines[0].split(',')
            tool_parameters_2 =  lines[1].split(',')
            
            self.tool_path = tool_parameters_1[0]
            self.tool_path = self.tool_path.split('/')
            self.tool_path =  self.tool_path[1]
            
            self.tool = tool_parameters_1[1]
            self.tool_name = tool_parameters_1[2]
            
            self.tool_data = tool_parameters_2[0]
            self.diameter = float(tool_parameters_2[1])
            self.lower_radius = float(tool_parameters_2[2])
            self.taper_angle = float(tool_parameters_2[3])
            self.tip_angle = float(tool_parameters_2[4])
            
            self.line_skip = 1
            
        # self.tool_number = Tool.tool_count
        # Tool.tool_count = Tool.tool_count + 1
        
        # Hardcoding these values because not available in CLSF File
        if self.tool_name == "MILL":
            self.speed = 1500
            self.tool_compensation_type = "G43"
        elif self.tool_name == "BALL_MILL":
            self.speed = 1500
            self.tool_compensation_type = "G234"
        elif self.tool_name == "MILL_MULTI_AXIS":
            self.speed = 1500
            self.tool_compensation_type = "G234"
        
# This is our CLSF to G-Code Translator
class CLSF_to_GCode():
    CLSF = []
    g_code = []
    current_coord = [0,0,0,0,0,1]
    current_coord_gcode = [0,0,0,0,0,0]
    n_index = 5
    CLSF_line_count = 0
    tools = {}
    DWO = False
    beta = 0
    gamma = 0
    
    # Key is operation number, value the tool
    operations = {}
    current_operation = 0
    total_operations = 0 # total number of operations 
    first_operation_move = False # First move of an operation 
    
    # HAAS UMC750 Parameters
    B_limit = True
    min_B_rotation = -35 # degrees
    max_B_rotation = 110 # degrees
    Z_limit = False
    
    # Current motion
    current_motion = 'G01'
    axes_lock = True
        
    def n_index_return(self):
        index = self.n_index
        self.n_index += 5
        return index
    
    def tool_table(self):
        self.g_code.append("(----------------- TOOL TABLE SUMMARY --------------------)")
        self.g_code.append(f"({'TOOL-NO.':<11}{'TOOL-NAME':<28}{'DIAMETER':<11}{'OFFSET':<7})")
        for key in self.tools:
            self.g_code.append(f"(   {key:<8}{self.tools[key].tool_name:<29}{self.tools[key].diameter:<11.4f}{self.tools[key].offset:<6})")
        self.g_code.append("(--------------END OF TOOL TABLE SUMMARY -----------------)")
        
        
    def new_operation(self):
        
        self.current_operation += 1
        
        tool = self.operations[self.current_operation]
        
        self.first_operation_move = True
        
        # Add these G-Code commands if this is the first opreation
        if self.current_operation == 1:
            self.tool_table()
            self.g_code.append("")
            self.g_code.append(f"N{self.n_index_return()} G40 G17 G94 G98 G90 G00 G49 G20)")
            self.g_code.append("")
            self.g_code.append(f"( *** TOOL CHANGE: T{tool.tool_number:02d}: {tool.tool_name} *** )")
            self.g_code.append("")
            self.g_code.append(f"( OPER: {tool.tool_path} )")
            self.g_code.append(f"N{self.n_index_return()} G53 G00 Z0.0")
        
        else:# For every new operation:
            self.g_code.append("")
            
            # Check to see tool change, if true then apply tool change header 
            if self.operations[self.current_operation].tool_number != self.operations[self.current_operation - 1].tool_number:
                self.g_code.append(f"( *** TOOL CHANGE: T{tool.tool_number:02d}: {tool.tool_name} *** )")
                self.g_code.append("")
                
            self.g_code.append(f"( OPER: {tool.tool_path} )")

        # Check if G254 (Dynamic Work Offsett) is active, if true then turn off (G255)
        if self.DWO:
            self.g_code.append(f"N{self.n_index_return()} G255")
            
        # self.g_code.append(f"N{self.n_index_return()} G53 G00 Z0.0")
        
        # Check to see tool change, if true then prepare for and apply tool change
        if self.current_operation == 1 or self.operations[self.current_operation].tool_number != self.operations[self.current_operation - 1].tool_number:
                      
            # Preparing G91 and G28 Commands for tool change (Make sure these coordinates are at 0)
            x = False
            y = False
            b = False
            c = False
                   
            if self.current_coord[0] != 0 or self.current_operation == 1:
                x = True
                
            if self.current_coord[1] != 0 or self.current_operation == 1:
                y = True
                
            if len(self.current_coord) > 3:
                if self.current_coord[3] != 0 or self.current_operation == 1:
                    b = True
                    
                if self.current_coord[4] != 0 or self.current_operation == 1:
                    c = True
                
            xy = f"N{self.n_index_return()} G91 G28 "
            bc = f"N{self.n_index_return()} G91 G28 "
                
            if x:
                xy = xy + "X0.0000 "
                
            if y:
                xy = xy + "Y0.0000 "
                
            if b:
                bc = bc + "B0.0000 "
                
            if c:
                bc = bc + "C0.0000 "
            
            self.g_code.append(xy)
            self.g_code.append(bc)
            
            if self.current_operation == 1:
                self.g_code.append(f"N{self.n_index_return()} G90")
        
        return tool.line_skip
    
    def load_tool(self):
        
        current_tool_number = self.operations[self.current_operation].tool_number
        current_tool_speed = self.operations[self.current_operation].speed
        self.g_code.append(f"N{self.n_index_return()} T{current_tool_number} M06")
        
        if self.current_operation + 1 in self.operations:     
            operation_total_count = len(self.operations)
            
            for n in range(self.current_operation + 1, operation_total_count + 1):
                next_tool_number = self.operations[n].tool_number
            
                if next_tool_number != current_tool_number:
                    self.g_code.append(f"N{self.n_index_return()} T{next_tool_number}")
                    break 
            
        self.g_code.append(f"N{self.n_index_return()} M01")
        self.g_code.append(f"N{self.n_index_return()} G53 G00 Z0.0")
        # self.current_coord[2] = 0
        # self.current_coord_gcode[2] = 0
        self.g_code.append(f"N{self.n_index_return()} S{current_tool_speed} M03")
        self.g_code.append(f"N{self.n_index_return()} G17 G54 G90")
        

# Given the target coordinates with tool axis vector
# Returns rotation B and C rotations (beta, gamma angles in degrees)
    def rotate(self, target_coord):
        beta = 90 
        gamma = 90
        r2d = 180/math.pi

        if target_coord[3] == 0 and target_coord[5] == 0:
            gamma = 90
            beta = 90
        
        elif target_coord[3] == 0:
            gamma = 90
            try:
                beta = abs(math.atan(target_coord[4]/target_coord[5])) * r2d
            except:
                print(CLSF_to_GCode.CLSF[self.CLSF_line_count])
                raise("Please don't let me come here")
            
            if target_coord[4] < 0:
                gamma = -90
               
        
        else:
            # we transform from [0,0,1] to target to find rotation
            # First rotate C (about the Z-Axis) - we align the x axis to xy direction of target vector 
            gamma = math.atan(target_coord[4]/target_coord[3]) * r2d
            
            xy = math.sqrt(target_coord[3]**2 + target_coord[4]**2)
            beta_prime = abs(math.atan(target_coord[5]/xy) * r2d)
            beta = 90 - beta_prime
            
            if target_coord[3] < 0:
                beta = -beta
                
        if beta < -35 or beta > 120:
            gamma = gamma - 180
            beta = -beta
        
        
        return beta, gamma 
        
    
    def linear(self, rapid, feed, target_coord):
        
        target_coord = target_coord
        motion = None
        motion_change = False
        skip = 0
        rotate = False
        
        # Handles motion change commands (E.g. G00, G01)
        if rapid:
            motion = 'G00'
        else:
            motion = 'G01'
            
        if motion == self.current_motion:
            motion_change = False
        else:
            self.current_motion = motion
            
        check_circle_line = CLSF_to_GCode.CLSF[self.CLSF_line_count-2]
        if 'CIRCLE' in check_circle_line:
            motion_change = True
            motion = 'G01'
            self.current_motion = motion
            
        # if self.CLSF_line_count < 30:
        #     print(target_coord)
            
        rotate = True
            
        if len(target_coord) > 3:
            i = target_coord[3]
            j = target_coord[4]
            k = target_coord[5]
            
            if i == 0 and j == 0 and k == 1:
                rotate = False
                self.beta = 0
                self.gamma = 0
                
        old_beta = self.beta
        old_gamma = self.gamma
            
        if len(target_coord) > 3 and rotate:
                self.beta, self.gamma = self.rotate(target_coord)
            
        if rotate:
            target_coord = self.rotate_coord(target_coord)
        
        x = True
        y = True
        z = True
                    
        if self.current_coord[0] == target_coord[0]:
            x = False
            
        if self.current_coord[1] == target_coord[1]:
            y = False
            
        if self.current_coord[2] == target_coord[2]:
            z = False
            
        string = f"N{self.n_index_return()} "
        
        if motion_change:
            string = string + f"{motion} "
            
        if x:
            string = string + f"X{target_coord[0]:.4f} "
            
        if y:
            string = string + f"Y{target_coord[1]:.4f} "
            
        if z:
            string = string + f"Z{target_coord[2]:.4f} "
            
        if old_beta != self.beta or old_gamma != self.gamma:
            string = string + f"B{self.beta:.4f} "
            
        if old_beta != self.beta or old_gamma != self.gamma: 
            string = string + f"C{self.gamma:.4f} "
        
        # if self.beta:
        #     string = string + f"B{self.beta:.4f} "
            
        # if self.gamma: 
        #     string = string + f"C{self.gamma:.4f} "
            
        if feed:
            string = string + f"F{feed:.4f} "
            
        self.g_code.append(string)
            
        self.current_coord = target_coord
        
        if rapid or feed:
            skip = 1
            
        if rapid and feed:
            skip = 2
            
        return skip 
                     
    def circular(self):
        
        skip = 1
        current_line = self.CLSF_line_count
        previous_line = current_line - 1
        next_line = current_line + 1
        
        
        target_coord = CLSF_to_GCode.CLSF[next_line].split('/')
        target_coord = target_coord[1].split(',')
        target_coord = [float(i) for i in target_coord]
        target_coord = self.rotate_coord(target_coord)
        
        circle_params = CLSF_to_GCode.CLSF[current_line].split('/')
        circle_params = circle_params[1].split(',')
        circle_params = [float(i) for i in circle_params]
        
        center_coord = [circle_params[0],circle_params[1],circle_params[2]]
        
        if self.beta != 0 or self.gamma != 0:
            center_coord = self.rotate_coord(center_coord)
        
        radius = circle_params[6]
        
        x_center = center_coord[0]
        y_center = center_coord[1]
        
        x_start = self.current_coord[0]
        y_start = self.current_coord[1]
        x_end = target_coord[0]
        y_end = target_coord[1]
        
        x_diff =  x_center - x_start
        y_diff = y_center - y_start
        
        feed = None 
        
        clockwise = self.arc_direction_clockwise(x_start,y_start,x_end,y_end,x_center,y_center,radius)
        
        if not clockwise:
            self.current_motion = "G03"
            
        if 'FEDRAT' in CLSF_to_GCode.CLSF[previous_line]:
            line = CLSF_to_GCode.CLSF[previous_line].split(',')
            feed = float(line[1])
            
        # -------------------------------------------------------------------------
        # This is a cheater method for dealing with helixes... We can add a helix
        # fnction in a future release
        if self.current_coord[2] != target_coord[2]:
            string = f"N{self.n_index_return()} G01 Z{target_coord[2]:.4f} " 
            if feed:
                string = string + f"F{feed:.4f} "
            self.g_code.append(string)
            feed = None 
        # -------------------------------------------------------------------------
            
        string = f"N{self.n_index_return()} "
            
        if clockwise:
            string = string + "G02 "
        else:
            string = string + "G03 "
            
        string = string + f"X{target_coord[0]:.4f} Y{target_coord[1]:.4f} I{x_diff:.4f} J{y_diff:.4f} "
            
        if feed:
            string = string + f"F{feed:.4f} "
            
        self.g_code.append(string)
            
        self.current_coord = target_coord
        
        return skip
    
    def arc_direction_clockwise(self,x_start,y_start,x_end,y_end,x_center,y_center,radius):
        
        # Translate all coordinates relative to origin
        
        x_start_new = x_start - x_center
        y_start_new = y_start - y_center
        
        x_end_new = x_end - x_center
        y_end_new = y_end - y_center
        # print(x_start_new)
        # print(x_end_new)
        # print(radius)
        
        start_quadrant = 0
        end_quadrant = 0
        
        if x_start_new >= 0 and y_start_new >= 0:
            start_quadrant = 1
        if x_start_new <= 0 and y_start_new >= 0:
            start_quadrant = 2
        if x_start_new <= 0 and y_start_new <= 0:
            start_quadrant = 3
        if x_start_new >= 0 and y_start_new <= 0:
            start_quadrant = 4
            
        if x_end_new >= 0 and y_end_new >= 0:
            end_quadrant = 1
        if x_end_new <= 0 and y_end_new >= 0:
            end_quadrant = 2
        if x_end_new <= 0 and y_end_new <= 0:
            end_quadrant = 3
        if x_end_new >= 0 and y_end_new <= 0:
            end_quadrant = 4
            
        ratio = x_start_new/radius
        if ratio > 1:
            ratio = 1
        if ratio < -1:
            ratio = -1
        
        x_start_angle = math.degrees(math.acos(ratio))
        
        if start_quadrant == 1:
            x_start_angle = x_start_angle
        if start_quadrant == 2:
            x_start_angle = x_start_angle
        if start_quadrant == 3:
            x_start_angle = x_start_angle + 90
        if start_quadrant == 4:
            x_start_angle == 360 - x_start_angle
            
        ratio = x_end_new/radius
        if ratio > 1:
            ratio = 1
        if ratio < -1:
            ratio = -1
        
        x_end_angle = math.degrees(math.acos(ratio))
         
        if end_quadrant == 1:
            x_end_angle = x_end_angle
        if end_quadrant == 2:
            x_end_angle = x_end_angle
        if end_quadrant == 3:
            x_end_angle = x_end_angle + 90
        if end_quadrant == 4:
            x_end_angle == 360 - x_end_angle
            
        # if x_end_angle < 0:
        #     x_end_angle + 360
            
        # if x_start_angle < 0:
        #     x_start_angle + 360
            
        if x_end_angle - x_start_angle >= 180:
            return True
        else:
            return False  
        
    def go_to(self):
        current_line = self.CLSF_line_count
        previous_line = current_line - 1
        # next_line = current_line + 1
        
        try:
            target_coord = CLSF_to_GCode.CLSF[current_line].split('/')
            target_coord = target_coord[1].split(',')
            target_coord = [float(i) for i in target_coord]
        except:
            print(CLSF_to_GCode.CLSF[current_line])
        
        rapid = False
        feed = None
        # circle = False
        
        
        if 'RAPID' in CLSF_to_GCode.CLSF[previous_line]:
            rapid = True
            
        if 'FEDRAT' in CLSF_to_GCode.CLSF[previous_line]:
            line = CLSF_to_GCode.CLSF[previous_line].split(',')
            feed = float(line[1])
            
        # if 'CIRCLE' in CLSF_to_GCode.CLSF[next_line]:
        #     circle = True
        #     self.circular(target_coord, next_line, feed)
            
        # if 'FEDRAT' in CLSF_to_GCode.CLSF[next_line]:
        #     if 'CIRCLE' in CLSF_to_GCode.CLSF[next_line + 1]:
        #         circle = True
        #         self.circular(target_coord, next_line + 1, feed) 

        # if not circle:
        self.linear(rapid, feed, target_coord)
            
    
    def start(self):
        self.g_code.append(f"N{self.n_index_return()} G40 G17 G94 G98 G90 G00 G49 G20")
    
    # Parameters:
    # CLSF_path (String) : Path of the CLSF File
    def parse_CLSF(self, CLSF_path):
        
        # Open and turn CLSF file into list of strings (by line)
        with open(CLSF_path) as CLSF_File:
            unstripped_CLSF = CLSF_File.readlines()
            CLSF_to_GCode.CLSF = [line.strip() for line in unstripped_CLSF]
        
        CLSF_to_GCode.CLSF = [line for line in CLSF_to_GCode.CLSF if not 'PAINT' in line]
        CLSF_to_GCode.CLSF = [line.split('$')[0] for line in CLSF_to_GCode.CLSF]
            
        # Scan and index all tools and operations --------------------------------------------
        operation_count = 0
        line_count = 0
        tool_count = 1
        tool_name_to_number = {}
        
        for line in CLSF_to_GCode.CLSF:
            # If we are changing tool...
            if 'TOOL PATH' in line:
                operation_count += 1
                # Make the tool object
                tool = Tool(line_count)
                tool.line_start = line_count
                
                # Add to tool dictionary
                if tool.tool_name not in tool_name_to_number:
                    tool_name_to_number[tool.tool_name] = tool_count
                    tool.tool_number = tool_count
                    self.tools[tool_count] = tool
                    tool_count += 1
                    
                # Adding Tool Number to tool
                if tool.tool_name in tool_name_to_number:
                    tool.tool_number = tool_name_to_number[tool.tool_name]
                
                # Index the new operation with that tool number
                self.operations[operation_count] = tool
                
            self.total_operations = operation_count
            line_count += 1
            # self.CLSF_line_count = line_count
            
        # # test
        # for key in self.operations:
        #     print(f"operation {key}: tool name: {self.operations[key].tool_name}")
        # for key in self.tools:
        #     print(f"tool {key}: tool name: {self.tools[key].tool_name}")
        # #---------------
                

        # ------------------------------------------------------------------------------------            
        
        skip = 0
            
        for line in self.CLSF:
            
            for key in self.dictionary:
                if skip:
                    skip -= 1
                    break
                
                if key in line:
                    skip = self.dictionary[key](self)
                    break
                    
            self.CLSF_line_count = self.CLSF_line_count + 1
            
    def end_of_path(self):
        self.g_code.append(f"N{self.n_index_return()} G255")
    
    
    
    def rotate_z_transform(self, target_coord, gamma):
        
        target_coord_result = target_coord[:]
        
        # while gamma < 0:
        #     gamma = gamma + 360
        
        theta = math.radians(gamma)
        
        rotation_matrix_z = [[math.cos(theta),  -math.sin(theta),       0,      0],
                            [math.sin(theta),  math.cos(theta),        0,      0],
                            [0,                0,                      1,      0],
                            [0,                0,                      0,      1]]
        
        rotation_matrix_z = np.array(rotation_matrix_z)
        
        target_coord_temp = [   [target_coord[0]],
                                [target_coord[1]],
                                [target_coord[2]],
                                [1]]
        
        target_coord_temp = np.array(target_coord_temp)
        
        rotated_coord = np.matmul(rotation_matrix_z, target_coord_temp)
        rotated_coord = rotated_coord.T
        
        target_coord_result[0] = rotated_coord[0][0]
        target_coord_result[1] = rotated_coord[0][1]
        target_coord_result[2] = rotated_coord[0][2]
        
        return target_coord_result

    def rotate_y_transform(self, target_coord, beta):
        
            target_coord_result = target_coord[:]
            
            # while beta < 0:
            #     beta = beta + 360
            
            theta = math.radians(beta)
            
            rotation_matrix_y = [[math.cos(theta),      0,      math.sin(theta),    0],
                                [0,                    1,      0,                  0],
                                [-math.sin(theta),     0,      math.cos(theta),    0],
                                [0,                    0,      0,                  1]]
            
            rotation_matrix_y = np.array(rotation_matrix_y)
            
            target_coord_temp = [   [target_coord[0]],
                                    [target_coord[1]],
                                    [target_coord[2]],
                                    [1]]
            
            target_coord_temp = np.array(target_coord_temp)
            
            rotated_coord = np.matmul(rotation_matrix_y, target_coord_temp)
            rotated_coord = rotated_coord.T
            
            target_coord_result[0] = rotated_coord[0][0]
            target_coord_result[1] = rotated_coord[0][1]
            target_coord_result[2] = rotated_coord[0][2]
            
            return target_coord_result
        
    # def rotated_coord(self, target_coord, beta, gamma):
    #     temp_coord = self.rotate_y_transform(target_coord, beta)
    #     final_coord = self.rotate_z_transform(temp_coord, gamma)
        
    #     return final_coord
    
    # Commands Dictionary
    dictionary = {}
    dictionary['TOOL PATH'] = new_operation
    dictionary['LOAD/TOOL'] = load_tool
    dictionary['GOTO'] = go_to
    dictionary['CIRCLE'] = circular
    dictionary['END-OF-PATH'] = end_of_path
    
    def rotate_coord(self,targ_coord):
        beta, gamma = self.beta, self.gamma
        gamma = gamma - 180
        targ_coord_temp = targ_coord[:]
        coord_temp = self.rotate_z_transform(targ_coord_temp, gamma)
        final_coord = self.rotate_y_transform(coord_temp, beta)
        final_coord[0] = -final_coord[0]
        final_coord[1] = -final_coord[1]
        return final_coord 

# Command Line Tool --------------------------------------------------------------------------

def usage():
    print("-h, --help: Display options")
    print("-i, --input: Input File")
    print("-o, --output: Output Files")
    

# Main function for command-line argument
def main():
    
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:o:", ["help", "input=","output="])
    except getopt.GetoptError as err:
        print(err)  
        usage()
        sys.exit(2)
        
    
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-i", "--input"):
            input = a
        elif o in ("-o", "--output"):
            output = a
        else:
            assert False, "unhandled option"
            
    if debug :
        output = 'g-code.txt'
        input = 'cls.txt'
            
    translator = CLSF_to_GCode()
    translator.parse_CLSF(input)
    
    g_code_output = open(output, "w")
    
    for line in CLSF_to_GCode.g_code:
        g_code_output.write(line + "\n")
    
    # #test
    # clsf = 'clsf_out.txt'
    # clsf_output = open(clsf,'w')
          
    # for line in CLSF_to_GCode.CLSF:
    #     clsf_output.write(line + "\n")
        
    g_code_output.close()  

if __name__ == "__main__":
    main()

