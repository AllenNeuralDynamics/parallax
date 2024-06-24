import numpy as np
import pyceres

class SnavelyReprojectionError(pyceres.CostFunction):
    def __init__(self, observed_x, observed_y):
        super(SnavelyReprojectionError, self).__init__()
        # observed 2D point on the image
        self.observed_x = observed_x
        self.observed_y = observed_y
        self.set_num_residuals(2)  # Diff between observed and predicted 2D point
        # Camera Parameters Block (size 12 - Angle-axis rotation (3 parameters), 
        # translation (3 parameters), focal length (1 parameter), radial distortion (3 parameters), tangential distortion (2 parameters))
        # Point Parameters Block (size 3 - 3D point in the world coordinate system)
        self.set_parameter_block_sizes([12, 3])  # Updated size to include tangential distortion coefficients

    def Evaluate(self, parameters, residuals, jacobians):
        camera = parameters[0]
        point = parameters[1]

        # Angle-axis rotation
        p = self.angle_axis_rotate_point(camera[:3], point)

        # Translation
        p[0] += camera[3]
        p[1] += camera[4]
        p[2] += camera[5]

        # Camera model projection
        xp = p[0] / p[2]
        yp = p[1] / p[2]

        # Radial and tangential distortion
        k1, k2, p1, p2, k3 = camera[7:12]

        r2 = xp * xp + yp * yp
        radial_distortion = 1 + k1 * r2 + k2 * r2 * r2 + k3 * r2 * r2 * r2
        x_distorted = xp * radial_distortion + 2 * p1 * xp * yp + p2 * (r2 + 2 * xp * xp)
        y_distorted = yp * radial_distortion + p1 * (r2 + 2 * yp * yp) + 2 * p2 * xp * yp

        # Apply focal length
        focal = camera[6]
        predicted_x = focal * x_distorted + 2000  # Apply Ox offset
        predicted_y = focal * y_distorted + 1500  # Apply Oy offset

        # Residuals
        residuals[0] = predicted_x - self.observed_x
        residuals[1] = predicted_y - self.observed_y

        # Debug: Print residuals and intermediate values
        print(f"Residuals: {residuals[0]}, {residuals[1]}")

        if jacobians is not None:
            jac_camera, jac_point = self.compute_jacobians(focal, k1, k2, p1, p2, k3, p, xp, yp, r2, radial_distortion)

            # Flatten the jacobians and fill the provided jacobians array
            if jacobians[0] is not None:
                jacobians[0][:] = jac_camera.ravel()
            if jacobians[1] is not None:
                jacobians[1][:] = jac_point.ravel()

        return True

    def angle_axis_rotate_point(self, angle_axis, point):
        theta = np.linalg.norm(angle_axis)
        if theta > 0:
            k = angle_axis / theta
            point_rot = (np.cos(theta) * point +
                         np.sin(theta) * np.cross(k, point) +
                         (1 - np.cos(theta)) * np.dot(k, point) * k)
        else:
            point_rot = point
        return point_rot

    def compute_jacobians(self, focal, k1, k2, p1, p2, k3, p, xp, yp, r2, radial_distortion):
        # Initialize the jacobians
        jac_camera = np.zeros((2, 12), dtype=np.float32)
        jac_point = np.zeros((2, 3), dtype=np.float32)

        # Derivatives of xp and yp
        dxp_dP = np.array([-1 / p[2], 0, p[0] / (p[2] * p[2])])
        dyp_dP = np.array([0, -1 / p[2], p[1] / (p[2] * p[2])])

        # Derivatives of distortion
        ddistortion_dr2 = k1 + 2 * k2 * r2 + 3 * k3 * r2 * r2
        dr2_dP = 2 * np.array([xp * dxp_dP, yp * dyp_dP])

        # Derivatives of predicted_x and predicted_y
        dpredicted_x_dP = focal * (radial_distortion * dxp_dP + xp * ddistortion_dr2 * dr2_dP[0])
        dpredicted_y_dP = focal * (radial_distortion * dyp_dP + yp * ddistortion_dr2 * dr2_dP[1])

        # Camera parameters jacobians
        jac_camera[0, 0:3] = dpredicted_x_dP[:3]  # w.r.t rotation
        jac_camera[1, 0:3] = dpredicted_y_dP[:3]  # w.r.t rotation
        jac_camera[0, 3:6] = focal * radial_distortion * np.array([-1 / p[2], 0, p[0] / (p[2] * p[2])])  # w.r.t translation
        jac_camera[1, 3:6] = focal * radial_distortion * np.array([0, -1 / p[2], p[1] / (p[2] * p[2])])  # w.r.t translation
        jac_camera[0, 6] = radial_distortion * xp  # w.r.t focal length
        jac_camera[1, 6] = radial_distortion * yp  # w.r.t focal length
        jac_camera[0, 7] = focal * xp * r2  # w.r.t k1
        jac_camera[1, 7] = focal * yp * r2  # w.r.t k1
        jac_camera[0, 8] = focal * xp * r2 * r2  # w.r.t k2
        jac_camera[1, 8] = focal * yp * r2 * r2  # w.r.t k2
        
        jac_camera[0, 9] = focal * (2 * xp * yp)  # w.r.t p1
        jac_camera[1, 9] = focal * (r2 + 2 * yp * yp)  # w.r.t p1
        jac_camera[0, 10] = focal * (r2 + 2 * xp * xp)  # w.r.t p2
        jac_camera[1, 10] = focal * (2 * xp * yp)  # w.r.t p2
        jac_camera[0, 11] = focal * xp * r2 * r2 * r2  # w.r.t k3
        jac_camera[1, 11] = focal * yp * r2 * r2 * r2  # w.r.t k3
        

        # Point parameters jacobians
        jac_point[0, :] = dpredicted_x_dP
        jac_point[1, :] = dpredicted_y_dP

        return jac_camera, jac_point

    @staticmethod
    def Create(observed_x, observed_y):
        return SnavelyReprojectionError(observed_x, observed_y)


class BundleAdjustment:
    def __init__(self, cam, coords, itmx):
        self.cam_name = cam
        self.coords_guess = coords
        self.itmx_guess = itmx

        self.coords_updates = None
        self.itmx_guess = None

    